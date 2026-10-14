import json
import tempfile
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .models import (
    Conversation,
    ConversationMember,
    Invitation,
    Message,
    MessageReceipt,
    RoomInvitation,
    User,
    UserFriend,
)
from .mqtt_messages import (
    CLIENT_EVENT_TOPIC,
    CONVERSATION_MESSAGE_TOPIC,
    CONVERSATION_READ_TOPIC,
    CLIENT_MESSAGE_CREATED_TOPIC,
    MessageCommandSubscriber,
)
from .mqtt_presence import PresenceSubscriber
from .services import ChatService, ServiceError


def link_profile(profile):
    auth_user = get_user_model().objects.create_user(
        username=profile.username,
        password="Test-Password-123!",
    )
    profile.auth_user = auth_user
    profile.save(update_fields=["auth_user"])
    return auth_user


def login_profile(client, profile):
    auth_user = profile.auth_user_id and profile.auth_user or link_profile(profile)
    client.force_login(auth_user)
    session = client.session
    session["chat_auth_expires_at"] = timezone.now().timestamp() + 8 * 60 * 60
    session.save()


class UserAvatarTests(TestCase):
    def setUp(self):
        media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.client = Client()
        self.user = User.objects.create(username="avatar-user")
        login_profile(self.client, self.user)
        self.url = f"/api/users/{self.user.user_id}/avatar/"

    def test_user_can_upload_and_remove_avatar(self):
        upload = SimpleUploadedFile(
            "profile.png",
            b"\x89PNG\r\n\x1a\navatar-bytes",
            content_type="image/png",
        )
        response = self.client.post(self.url, {"avatar": upload})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["avatar_url"].endswith(".png"))
        self.user.refresh_from_db()
        stored_avatar = self.user.avatar.path
        self.assertTrue(self.user.avatar.storage.exists(self.user.avatar.name))

        replacement = SimpleUploadedFile(
            "replacement.gif",
            b"GIF89aavatar-bytes",
            content_type="image/gif",
        )
        response = self.client.post(self.url, {"avatar": replacement})

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar.storage.exists(stored_avatar))
        stored_avatar = self.user.avatar.path

        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["avatar_url"])
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)
        self.assertFalse(self.user.avatar.storage.exists(stored_avatar))

    def test_rejects_non_image_avatar(self):
        upload = SimpleUploadedFile("profile.txt", b"not an image")

        response = self.client.post(self.url, {"avatar": upload})

        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.avatar)

    def test_rejects_avatar_larger_than_limit(self):
        upload = SimpleUploadedFile(
            "large.png",
            b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024),
        )

        response = self.client.post(self.url, {"avatar": upload})

        self.assertEqual(response.status_code, 400)


class MessageReplyTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create(username="sender")
        self.conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )

    def create_message(self, seq, content, reply_to=None):
        return Message.objects.create(
            client_message_id=f"client-{seq}",
            conversation=self.conversation,
            sender=self.sender,
            content=content,
            seq=seq,
            reply_to=reply_to,
        )

    def test_message_can_reply_to_another_message(self):
        original = self.create_message(1, "original")
        reply = self.create_message(2, "reply", reply_to=original)

        reply.refresh_from_db()
        self.assertEqual(reply.reply_to, original)
        self.assertEqual(list(original.replies.all()), [reply])

    def test_deleting_original_message_clears_reply_relation(self):
        original = self.create_message(1, "original")
        reply = self.create_message(2, "reply", reply_to=original)

        original.delete()

        reply.refresh_from_db()
        self.assertIsNone(reply.reply_to)


class UserProfileApiTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_create_and_patch_user_profile(self):
        response = self.client.post(
            "/api/auth/register/",
            data=json.dumps(
                {
                    "username": "profile-user",
                    "password": "Profile-Password-123!",
                    "password_confirm": "Profile-Password-123!",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        user_id = response.json()["user"]["user_id"]
        self.assertTrue(User.objects.get(user_id=user_id).auth_user.check_password("Profile-Password-123!"))
        self.client.post(
            "/api/auth/login/",
            data=json.dumps(
                {"username": "profile-user", "password": "Profile-Password-123!"}
            ),
            content_type="application/json",
        )

        response = self.client.patch(
            f"/api/users/{user_id}/",
            data=json.dumps(
                {"short_bio": "IoT learner", "bio": "Updated bio", "sex": "male"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bio"], "Updated bio")
        self.assertEqual(response.json()["short_bio"], "IoT learner")
        self.assertEqual(response.json()["sex"], "male")
        self.assertEqual(response.json()["status"], "offline")

    def test_rejects_invalid_profile_values(self):
        response = self.client.post(
            "/api/users/",
            data=json.dumps({"username": "bad-user", "sex": "other"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 410)
        self.assertFalse(User.objects.filter(username="bad-user").exists())


class FriendsApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(username="friend-list-owner")
        self.friend = User.objects.create(username="friend-entry")
        login_profile(self.client, self.user)
        link_profile(self.friend)
        UserFriend.objects.bulk_create(
            [
                UserFriend(user=self.user, friend=self.friend),
                UserFriend(user=self.friend, friend=self.user),
            ]
        )

    def test_list_friends_returns_friend_users(self):
        response = self.client.get(f"/api/users/{self.user.user_id}/friends/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [friend["username"] for friend in response.json()["friends"]],
            ["friend-entry"],
        )

    def test_list_friends_uses_keyset_pages_and_online_filter(self):
        friends = [
            User.objects.create(username="friend-a", status=User.PresenceStatus.ONLINE),
            User.objects.create(username="friend-b"),
        ]
        for friend in friends:
            link_profile(friend)
            UserFriend.objects.bulk_create(
                [
                    UserFriend(user=self.user, friend=friend),
                    UserFriend(user=friend, friend=self.user),
                ]
            )

        first_page = self.client.get(
            f"/api/users/{self.user.user_id}/friends/",
            {"limit": 2},
        )
        self.assertEqual(first_page.status_code, 200)
        payload = first_page.json()
        self.assertEqual(payload["total"], 3)
        self.assertEqual(payload["online_total"], 1)
        self.assertEqual(len(payload["friends"]), 2)
        self.assertIsNotNone(payload["next_cursor"])

        second_page = self.client.get(
            f"/api/users/{self.user.user_id}/friends/",
            {"limit": 2, "cursor": payload["next_cursor"]},
        )
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(len(second_page.json()["friends"]), 1)
        self.assertIsNone(second_page.json()["next_cursor"])

        online = self.client.get(
            f"/api/users/{self.user.user_id}/friends/",
            {"online": "true"},
        )
        self.assertEqual(
            [friend["username"] for friend in online.json()["friends"]],
            ["friend-a"],
        )

    def test_list_friends_rejects_invalid_cursor(self):
        response = self.client.get(
            f"/api/users/{self.user.user_id}/friends/",
            {"cursor": str(uuid.uuid4())},
        )
        self.assertEqual(response.status_code, 400)

    def test_list_invitations_returns_incoming_and_sent_pending_requests(self):
        incoming_sender = User.objects.create(username="incoming-sender")
        outgoing_recipient = User.objects.create(username="outgoing-recipient")
        Invitation.objects.create(sender=incoming_sender, user=self.user)
        Invitation.objects.create(sender=self.user, user=outgoing_recipient)
        link_profile(incoming_sender)
        link_profile(outgoing_recipient)
        Invitation.objects.create(
            sender=incoming_sender,
            user=self.user,
            status=Invitation.InvitationStatus.REJECT,
        )

        response = self.client.get(
            f"/api/users/{self.user.user_id}/invitations/"
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(len(result["incoming"]), 1)
        self.assertEqual(result["incoming"][0]["sender"]["username"], "incoming-sender")
        self.assertEqual(result["incoming"][0]["recipient"]["username"], self.user.username)
        self.assertEqual(len(result["sent"]), 1)
        self.assertEqual(result["sent"][0]["recipient"]["username"], "outgoing-recipient")


class ConversationApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.alex = User.objects.create(username="alex")
        self.sarah = User.objects.create(username="sarah")
        self.kevin = User.objects.create(username="kevin")
        login_profile(self.client, self.alex)
        link_profile(self.sarah)
        link_profile(self.kevin)

    def post_json(self, url, body, headers=None):
        return self.client.post(
            url,
            data=json.dumps(body),
            content_type="application/json",
            headers=headers,
        )

    def test_private_conversation_is_reused_with_exact_members(self):
        response = self.post_json(
            "/api/conversations/",
            {
                "user_id": str(self.alex.user_id),
                "type": "PRIVATE",
                "username": "sarah",
            },
        )
        conversation_id = response.json()["conversation_id"]
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            set(
                ConversationMember.objects.filter(
                    conversation_id=conversation_id
                ).values_list("user_id", flat=True)
            ),
            {self.alex.user_id, self.sarah.user_id},
        )

        login_profile(self.client, self.sarah)
        repeated = self.post_json(
            "/api/conversations/",
            {
                "user_id": str(self.sarah.user_id),
                "type": "PRIVATE",
                "username": "alex",
            },
        )
        self.assertEqual(repeated.status_code, 201)
        self.assertEqual(repeated.json()["conversation_id"], conversation_id)
        self.assertEqual(Conversation.objects.count(), 1)

    def test_group_members_are_created_from_existing_user_records(self):
        response = self.post_json(
            "/api/conversations/",
            {
                "user_id": str(self.alex.user_id),
                "type": "GROUP",
                "name": "Study group",
                "usernames": ["sarah", "kevin", "alex", "sarah"],
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["name"], "Study group")
        group = Conversation.objects.get(
            conversation_id=response.json()["conversation_id"]
        )
        self.assertEqual(group.owner_id, self.alex.user_id)
        self.assertEqual(
            set(
                ConversationMember.objects.filter(
                    conversation=group, is_active=True
                ).values_list("user_id", flat=True)
            ),
            {self.alex.user_id},
        )
        self.assertEqual(
            set(group.room_invitations.values_list("user_id", flat=True)),
            {self.sarah.user_id, self.kevin.user_id},
        )

    def test_list_user_conversations_includes_members_and_latest_message(self):
        older_conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        newer_conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.GROUP,
            name="Newer group",
        )
        empty_conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        unrelated_conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        ConversationMember.objects.bulk_create(
            [
                ConversationMember(conversation=older_conversation, user=self.alex),
                ConversationMember(conversation=older_conversation, user=self.sarah),
                ConversationMember(conversation=newer_conversation, user=self.alex),
                ConversationMember(conversation=newer_conversation, user=self.kevin),
                ConversationMember(conversation=empty_conversation, user=self.alex),
                ConversationMember(conversation=empty_conversation, user=self.sarah),
                ConversationMember(conversation=unrelated_conversation, user=self.sarah),
                ConversationMember(conversation=unrelated_conversation, user=self.kevin),
            ]
        )
        older_message = Message.objects.create(
            client_message_id="catalog-old",
            conversation=older_conversation,
            sender=self.sarah,
            content="Older message",
            seq=1,
        )
        latest_message = Message.objects.create(
            client_message_id="catalog-new",
            conversation=newer_conversation,
            sender=self.kevin,
            content="Latest message",
            seq=1,
        )
        Message.objects.filter(message_id=older_message.message_id).update(
            created_at=latest_message.created_at - timedelta(minutes=1)
        )

        response = self.client.get(
            f"/api/users/{self.alex.user_id}/conversations/"
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()["conversations"]
        self.assertEqual(
            [item["conversation_id"] for item in result],
            [
                str(newer_conversation.conversation_id),
                str(older_conversation.conversation_id),
                str(empty_conversation.conversation_id),
            ],
        )
        self.assertEqual(result[0]["type"], Conversation.ConversationType.GROUP)
        self.assertEqual(
            {member["username"] for member in result[0]["members"]},
            {"alex", "kevin"},
        )
        self.assertEqual(
            result[0]["last_message"]["message_id"], str(latest_message.message_id)
        )
        self.assertEqual(result[0]["unread_count"], 1)
        self.assertEqual(result[0]["last_message"]["content"], "Latest message")
        self.assertEqual(result[0]["last_message"]["sender"]["username"], "kevin")
        self.assertEqual(result[1]["last_message"]["sender"]["username"], "sarah")
        self.assertEqual(result[1]["unread_count"], 1)
        self.assertIsNone(result[2]["last_message"])
        self.assertEqual(result[2]["unread_count"], 0)

        MessageReceipt.objects.create(
            message=older_message,
            user=self.alex,
            status=MessageReceipt.ReceiptStatus.READ,
        )
        refreshed = self.client.get(
            f"/api/users/{self.alex.user_id}/conversations/"
        ).json()["conversations"]
        older_data = next(
            item for item in refreshed
            if item["conversation_id"] == str(older_conversation.conversation_id)
        )
        self.assertEqual(older_data["unread_count"], 0)

    def test_list_user_conversations_returns_empty_list_and_rejects_unknown_user(self):
        response = self.client.get(
            f"/api/users/{self.alex.user_id}/conversations/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"conversations": []})

        response = self.client.get(
            f"/api/users/{uuid.uuid4()}/conversations/"
        )
        self.assertEqual(response.status_code, 403)

    def test_rejects_group_with_unknown_username_without_creating_members(self):
        response = self.post_json(
            "/api/conversations/",
            {
                "user_id": str(self.alex.user_id),
                "type": "GROUP",
                "usernames": ["missing-user"],
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Conversation.objects.exists())
        self.assertFalse(ConversationMember.objects.exists())

    def test_room_invitation_accept_adds_recipient_to_group(self):
        group = Conversation.objects.create(
            name="Project team",
            conversation_type=Conversation.ConversationType.GROUP,
            owner=self.alex,
        )
        ConversationMember.objects.create(conversation=group, user=self.alex)
        response = self.post_json(
            "/api/room-invitations/",
            {
                "sender_id": str(self.alex.user_id),
                "user_id": str(self.sarah.user_id),
                "conversation_id": str(group.conversation_id),
            },
            headers={"If-Match": '"1"'},
        )
        self.assertEqual(response.status_code, 201)
        invitation_id = response.json()["invitation_id"]

        login_profile(self.client, self.sarah)
        inbox = self.client.get(
            f"/api/users/{self.sarah.user_id}/invitations/"
        ).json()
        self.assertEqual(len(inbox["room_incoming"]), 1)
        self.assertEqual(
            inbox["room_incoming"][0]["conversation"]["name"], "Project team"
        )
        self.assertEqual(len(inbox["room_sent"]), 0)

        response = self.post_json(
            f"/api/room-invitations/{invitation_id}/respond/",
            {"status": "ACCEPT"},
            headers={"If-Match": '"2"'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            ConversationMember.objects.filter(
                conversation=group, user=self.sarah
            ).exists()
        )
        self.assertEqual(
            RoomInvitation.objects.get(invitation_id=invitation_id).status,
            RoomInvitation.InvitationStatus.ACCEPT,
        )

    def test_room_invitation_reject_and_sender_permission(self):
        group = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.GROUP,
            owner=self.alex,
        )
        ConversationMember.objects.create(conversation=group, user=self.alex)
        non_member_send = self.post_json(
            "/api/room-invitations/",
            {
                "sender_id": str(self.kevin.user_id),
                "user_id": str(self.sarah.user_id),
                "conversation_id": str(group.conversation_id),
            },
        )
        self.assertEqual(non_member_send.status_code, 403)

        invitation = RoomInvitation.objects.create(
            conversation=group,
            sender=self.alex,
            user=self.sarah,
        )
        login_profile(self.client, self.sarah)
        rejected = self.post_json(
            f"/api/room-invitations/{invitation.invitation_id}/respond/",
            {"status": "REJECT"},
            headers={"If-Match": '"1"'},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertFalse(
            ConversationMember.objects.filter(
                conversation=group, user=self.sarah
            ).exists()
        )

    def test_history_requires_membership_and_returns_chronological_messages(self):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        ConversationMember.objects.bulk_create(
            [
                ConversationMember(conversation=conversation, user=self.alex),
                ConversationMember(conversation=conversation, user=self.sarah),
            ]
        )
        first = Message.objects.create(
            client_message_id="history-1",
            conversation=conversation,
            sender=self.alex,
            content="first",
            seq=1,
        )
        second = Message.objects.create(
            client_message_id="history-2",
            conversation=conversation,
            sender=self.sarah,
            content="second",
            seq=2,
            reply_to=first,
        )
        MessageReceipt.objects.create(
            message=second,
            user=self.alex,
            status=MessageReceipt.ReceiptStatus.READ,
        )

        response = self.client.get(
            f"/api/conversations/{conversation.conversation_id}/messages/",
            {"user_id": str(self.alex.user_id), "limit": 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["content"] for item in response.json()["messages"]], ["second"])
        self.assertEqual(
            response.json()["messages"][0]["reply_to"]["message_id"],
            str(first.message_id),
        )
        self.assertEqual(
            response.json()["messages"][0]["read_by"][0]["user_id"],
            str(self.alex.user_id),
        )

        forbidden = self.client.get(
            f"/api/conversations/{conversation.conversation_id}/messages/",
            {"user_id": str(self.kevin.user_id)},
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_search_messages_matches_content_within_conversation(self):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        other_conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        ConversationMember.objects.bulk_create(
            [
                ConversationMember(conversation=conversation, user=self.alex),
                ConversationMember(conversation=conversation, user=self.sarah),
                ConversationMember(conversation=other_conversation, user=self.alex),
                ConversationMember(conversation=other_conversation, user=self.kevin),
            ]
        )
        Message.objects.create(
            client_message_id="search-hit-1",
            conversation=conversation,
            sender=self.alex,
            content="Project status is ready",
            seq=1,
        )
        Message.objects.create(
            client_message_id="search-miss",
            conversation=conversation,
            sender=self.sarah,
            content="A different update",
            seq=2,
        )
        Message.objects.create(
            client_message_id="search-hit-2",
            conversation=conversation,
            sender=self.sarah,
            content="READY for review",
            seq=3,
        )
        Message.objects.create(
            client_message_id="search-other-conversation",
            conversation=other_conversation,
            sender=self.alex,
            content="Ready in another conversation",
            seq=1,
        )

        response = self.client.get(
            f"/api/conversations/{conversation.conversation_id}/messages/search/",
            {"user_id": str(self.alex.user_id), "q": "ready"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["content"] for item in response.json()["messages"]],
            ["Project status is ready", "READY for review"],
        )

    def test_search_messages_requires_membership_and_nonempty_query(self):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        ConversationMember.objects.create(
            conversation=conversation,
            user=self.alex,
        )

        forbidden = self.client.get(
            f"/api/conversations/{conversation.conversation_id}/messages/search/",
            {"user_id": str(self.kevin.user_id), "q": "ready"},
        )
        missing_query = self.client.get(
            f"/api/conversations/{conversation.conversation_id}/messages/search/",
            {"user_id": str(self.alex.user_id), "q": "  "},
        )

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(missing_query.status_code, 400)


class MqttPresenceTests(TransactionTestCase):
    def test_presence_message_updates_the_persisted_user_status(self):
        user = User.objects.create(username="mqtt-user")
        subscriber = PresenceSubscriber(client=Mock())
        message = SimpleNamespace(
            topic=f"chat/users/{user.user_id}/status",
            payload=b"online",
        )

        subscriber.on_message(None, None, message)

        user.refresh_from_db()
        self.assertEqual(user.status, User.PresenceStatus.ONLINE)

    def test_invalid_presence_payload_is_ignored(self):
        user = User.objects.create(username="mqtt-user")
        subscriber = PresenceSubscriber(client=Mock())
        message = SimpleNamespace(
            topic=f"chat/users/{user.user_id}/status",
            payload=b"away",
        )

        subscriber.on_message(None, None, message)

        user.refresh_from_db()
        self.assertEqual(user.status, User.PresenceStatus.OFFLINE)


class MqttMessageTests(TransactionTestCase):
    def setUp(self):
        self.sender = User.objects.create(username="message-sender")
        self.recipient = User.objects.create(username="message-recipient")
        self.outsider = User.objects.create(username="message-outsider")
        self.conversation = Conversation.objects.create(
            conversation_type=Conversation.ConversationType.PRIVATE
        )
        ConversationMember.objects.bulk_create(
            [
                ConversationMember(
                    conversation=self.conversation,
                    user=self.sender,
                ),
                ConversationMember(
                    conversation=self.conversation,
                    user=self.recipient,
                ),
            ]
        )
        self.client = Mock()
        self.client.publish.return_value.rc = 0
        self.subscriber = MessageCommandSubscriber(client=self.client)

    def command(self, payload, sender=None):
        return SimpleNamespace(
            topic=(
                "chat/client/"
                f"{sender or self.sender.user_id}/command/send"
            ),
            payload=json.dumps(payload).encode("utf-8"),
        )

    def read_command(self, payload, sender=None):
        return SimpleNamespace(
            topic=(
                "chat/client/"
                f"{sender or self.recipient.user_id}/command/read"
            ),
            payload=json.dumps(payload).encode("utf-8"),
        )

    def test_worker_subscribes_to_send_and_read_commands(self):
        self.subscriber.on_connect(
            self.client,
            None,
            None,
            SimpleNamespace(is_failure=False),
            None,
        )

        subscribed_topics = [
            call.args[0] for call in self.client.subscribe.call_args_list
        ]
        self.assertIn("chat/client/+/command/send", subscribed_topics)
        self.assertIn("chat/client/+/command/read", subscribed_topics)

    def test_send_persists_message_and_publishes_acceptance_and_created(self):
        client_message_id = str(uuid.uuid4())
        self.subscriber.on_message(
            self.client,
            None,
            self.command(
                {
                    "conversation_id": str(self.conversation.conversation_id),
                    "client_message_id": client_message_id,
                    "content": "Hello",
                    "reply_to_message_id": None,
                }
            ),
        )

        saved = Message.objects.get(client_message_id=client_message_id)
        self.conversation.refresh_from_db()
        self.assertEqual(saved.sender, self.sender)
        self.assertEqual(saved.seq, 1)
        self.assertEqual(self.conversation.last_seq, 1)
        self.assertEqual(self.client.publish.call_count, 3)

        published = self.client.publish.call_args_list
        self.assertEqual(
            published[0].args[0],
            CLIENT_EVENT_TOPIC.format(
                user_id=self.sender.user_id,
                event="message_accepted",
            ),
        )
        accepted = json.loads(published[0].args[1])
        self.assertEqual(accepted["type"], "MESSAGE_ACCEPTED")
        self.assertEqual(accepted["client_message_id"], client_message_id)
        self.assertEqual(accepted["seq"], 1)
        self.assertFalse(accepted["duplicate"])
        self.assertEqual(
            published[1].args[0],
            CONVERSATION_MESSAGE_TOPIC.format(
                conversation_id=self.conversation.conversation_id
            ),
        )
        self.assertEqual(json.loads(published[1].args[1])["type"], "MESSAGE_CREATED")
        self.assertEqual(
            published[2].args[0],
            CLIENT_MESSAGE_CREATED_TOPIC.format(user_id=self.recipient.user_id),
        )
        self.assertEqual(
            json.loads(published[2].args[1]),
            {
                "type": "MESSAGE_CREATED",
                "notification_only": True,
                "conversation_id": str(self.conversation.conversation_id),
                "message_id": str(saved.message_id),
                "sender_id": str(self.sender.user_id),
                "seq": saved.seq,
                "created_at": saved.created_at.isoformat(),
            },
        )

    def test_duplicate_retry_is_accepted_without_allocating_a_new_sequence(self):
        payload = {
            "conversation_id": str(self.conversation.conversation_id),
            "client_message_id": str(uuid.uuid4()),
            "content": "Retry safely",
            "reply_to_message_id": None,
        }
        self.subscriber.on_message(self.client, None, self.command(payload))
        self.subscriber.on_message(self.client, None, self.command(payload))

        self.conversation.refresh_from_db()
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(self.conversation.last_seq, 1)
        self.assertEqual(self.client.publish.call_count, 4)
        retry_ack = json.loads(self.client.publish.call_args_list[3].args[1])
        self.assertEqual(retry_ack["type"], "MESSAGE_ACCEPTED")
        self.assertTrue(retry_ack["duplicate"])

    def test_each_new_message_gets_the_next_server_sequence(self):
        for content in ("First", "Second"):
            self.subscriber.on_message(
                self.client,
                None,
                self.command(
                    {
                        "conversation_id": str(self.conversation.conversation_id),
                        "client_message_id": str(uuid.uuid4()),
                        "content": content,
                        "reply_to_message_id": None,
                    }
                ),
            )

        self.conversation.refresh_from_db()
        self.assertEqual(
            list(
                Message.objects.filter(conversation=self.conversation)
                .order_by("seq")
                .values_list("seq", flat=True)
            ),
            [1, 2],
        )
        self.assertEqual(self.conversation.last_seq, 2)

    def test_read_command_persists_receipt_and_broadcasts_it_once(self):
        saved_message = Message.objects.create(
            client_message_id=str(uuid.uuid4()),
            conversation=self.conversation,
            sender=self.sender,
            content="Please read",
            seq=1,
        )
        payload = {
            "conversation_id": str(self.conversation.conversation_id),
            "message_ids": [str(saved_message.message_id)],
        }

        self.subscriber.on_message(
            self.client, None, self.read_command(payload)
        )

        receipt = MessageReceipt.objects.get(
            message=saved_message,
            user=self.recipient,
        )
        self.assertEqual(receipt.status, MessageReceipt.ReceiptStatus.READ)
        self.assertEqual(self.client.publish.call_count, 1)
        topic, raw_event = self.client.publish.call_args.args[:2]
        self.assertEqual(
            topic,
            CONVERSATION_READ_TOPIC.format(
                conversation_id=self.conversation.conversation_id
            ),
        )
        event = json.loads(raw_event)
        self.assertEqual(event["type"], "MESSAGE_READ")
        self.assertEqual(event["reader_id"], str(self.recipient.user_id))
        self.assertEqual(event["message_ids"], [str(saved_message.message_id)])

        self.subscriber.on_message(
            self.client, None, self.read_command(payload)
        )
        self.assertEqual(MessageReceipt.objects.count(), 1)
        self.assertEqual(self.client.publish.call_count, 1)

    def test_read_command_cannot_mark_messages_for_non_members(self):
        saved_message = Message.objects.create(
            client_message_id=str(uuid.uuid4()),
            conversation=self.conversation,
            sender=self.sender,
            content="Private",
            seq=1,
        )
        self.subscriber.on_message(
            self.client,
            None,
            self.read_command(
                {
                    "conversation_id": str(self.conversation.conversation_id),
                    "message_ids": [str(saved_message.message_id)],
                },
                sender=self.outsider.user_id,
            ),
        )

        self.assertFalse(MessageReceipt.objects.exists())
        error_payload = json.loads(self.client.publish.call_args.args[1])
        self.assertEqual(error_payload["type"], "ERROR")
        self.assertIn("not a member", error_payload["error"])

    def test_sender_must_be_a_conversation_member(self):
        self.subscriber.on_message(
            self.client,
            None,
            self.command(
                {
                    "conversation_id": str(self.conversation.conversation_id),
                    "client_message_id": str(uuid.uuid4()),
                    "content": "Not allowed",
                    "reply_to_message_id": None,
                },
                sender=self.outsider.user_id,
            ),
        )

        self.assertFalse(Message.objects.exists())
        self.assertEqual(self.client.publish.call_count, 1)
        error_topic, error_payload = self.client.publish.call_args.args[:2]
        self.assertEqual(
            error_topic,
            CLIENT_EVENT_TOPIC.format(
                user_id=self.outsider.user_id,
                event="error",
            ),
        )
        self.assertEqual(json.loads(error_payload)["type"], "ERROR")

    def test_client_cannot_supply_server_sequence(self):
        self.subscriber.on_message(
            self.client,
            None,
            self.command(
                {
                    "conversation_id": str(self.conversation.conversation_id),
                    "client_message_id": str(uuid.uuid4()),
                    "content": "Client sequence is not trusted",
                    "seq": 1,
                }
            ),
        )

        self.assertFalse(Message.objects.exists())
        error_payload = json.loads(self.client.publish.call_args.args[1])
        self.assertEqual(error_payload["type"], "ERROR")
        self.assertIn("seq is assigned by the server", error_payload["error"])


class AuthenticatedApiTests(TestCase):
    def test_registration_login_csrf_and_session_restore(self):
        client = Client(enforce_csrf_checks=True)
        rejected = client.post(
            "/api/auth/register/",
            data=json.dumps(
                {
                    "username": "csrf-user",
                    "password": "Secure-Password-123!",
                    "password_confirm": "Secure-Password-123!",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.json()["error"], "CSRF verification failed")

        token_response = client.get("/api/auth/csrf/")
        token = token_response.json()["csrfToken"]
        registered = client.post(
            "/api/auth/register/",
            data=json.dumps(
                {
                    "username": "csrf-user",
                    "password": "Secure-Password-123!",
                    "password_confirm": "Secure-Password-123!",
                }
            ),
            content_type="application/json",
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(registered.status_code, 201)
        self.assertTrue(
            User.objects.get(username="csrf-user").auth_user.check_password(
                "Secure-Password-123!"
            )
        )

        login_response = client.post(
            "/api/auth/login/",
            data=json.dumps(
                {
                    "username": "csrf-user",
                    "password": "Secure-Password-123!",
                    "remember_me": True,
                }
            ),
            content_type="application/json",
            headers={"X-CSRFToken": client.cookies["csrftoken"].value},
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response["Cache-Control"], "no-store")
        self.assertIn("csrfToken", login_response.json())
        restored = client.get("/api/auth/me/")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["user"]["username"], "csrf-user")

    def test_expired_or_missing_session_cannot_use_protected_api(self):
        client = Client()
        self.assertEqual(client.get("/api/users/search/").status_code, 401)

        profile = User.objects.create(username="expired-user")
        login_profile(client, profile)
        session = client.session
        session["chat_auth_expires_at"] = timezone.now().timestamp() - 1
        session.save()
        response = client.get(f"/api/users/{profile.user_id}/friends/")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(client.get("/api/auth/me/").status_code, 401)

    def test_legacy_user_creation_endpoint_is_disabled(self):
        response = Client().post(
            "/api/users/",
            data=json.dumps({"username": "legacy-user"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 410)
        self.assertFalse(User.objects.filter(username="legacy-user").exists())


class GroupManagementApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.owner = User.objects.create(username="group-owner")
        self.admin = User.objects.create(username="group-admin")
        self.member = User.objects.create(username="group-member")
        self.other = User.objects.create(username="group-outsider")
        for profile in (self.admin, self.member, self.other):
            link_profile(profile)
        login_profile(self.client, self.owner)
        self.group = Conversation.objects.create(
            name="Original name",
            description="Original description",
            conversation_type=Conversation.ConversationType.GROUP,
            owner=self.owner,
        )
        ConversationMember.objects.bulk_create(
            [
                ConversationMember(conversation=self.group, user=self.owner),
                ConversationMember(
                    conversation=self.group,
                    user=self.admin,
                    role=ConversationMember.Role.ADMIN,
                ),
                ConversationMember(conversation=self.group, user=self.member),
            ]
        )

    def test_group_detail_is_member_only_and_reports_permissions(self):
        RoomInvitation.objects.create(
            conversation=self.group,
            sender=self.owner,
            user=self.other,
        )
        detail = self.client.get(f"/api/conversations/{self.group.conversation_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["role"], "OWNER")
        self.assertTrue(detail.json()["permissions"]["can_manage_roles"])
        self.assertEqual(
            [person["username"] for person in detail.json()["pending_invitations"]],
            [self.other.username],
        )

        login_profile(self.client, self.other)
        denied = self.client.get(f"/api/conversations/{self.group.conversation_id}/")
        self.assertEqual(denied.status_code, 403)

    def test_group_update_requires_version_and_enforces_roles(self):
        login_profile(self.client, self.member)
        denied = self.client.patch(
            f"/api/conversations/{self.group.conversation_id}/",
            data=json.dumps({"name": "forged"}),
            content_type="application/json",
            headers={"If-Match": '"1"'},
        )
        self.assertEqual(denied.status_code, 403)
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, "Original name")

        login_profile(self.client, self.owner)
        missing = self.client.patch(
            f"/api/conversations/{self.group.conversation_id}/",
            data=json.dumps({"name": "Renamed"}),
            content_type="application/json",
        )
        self.assertEqual(missing.status_code, 428)
        updated = self.client.patch(
            f"/api/conversations/{self.group.conversation_id}/",
            data=json.dumps({"name": "Renamed", "description": "Updated"}),
            content_type="application/json",
            headers={"If-Match": '"1"'},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["version"], 2)
        stale = self.client.patch(
            f"/api/conversations/{self.group.conversation_id}/",
            data=json.dumps({"name": "Stale write"}),
            content_type="application/json",
            headers={"If-Match": '"1"'},
        )
        self.assertEqual(stale.status_code, 412)

    def test_admin_can_remove_member_but_cannot_remove_admin_or_owner(self):
        login_profile(self.client, self.admin)
        url = f"/api/conversations/{self.group.conversation_id}/members/"
        denied_owner = self.client.delete(
            f"{url}{self.owner.user_id}/",
            headers={"If-Match": '"1"'},
        )
        self.assertEqual(denied_owner.status_code, 409)
        removed = self.client.delete(
            f"{url}{self.member.user_id}/",
            headers={"If-Match": '"1"'},
        )
        self.assertEqual(removed.status_code, 200)
        self.assertFalse(
            ConversationMember.objects.get(
                conversation=self.group, user=self.member
            ).is_active
        )

    def test_owner_can_transfer_then_old_owner_leave(self):
        target_url = f"/api/conversations/{self.group.conversation_id}/transfer-ownership/"
        transferred = self.client.post(
            target_url,
            data=json.dumps({"new_owner_id": str(self.member.user_id)}),
            content_type="application/json",
            headers={"If-Match": '"1"'},
        )
        self.assertEqual(transferred.status_code, 200)
        self.group.refresh_from_db()
        self.assertEqual(self.group.owner_id, self.member.user_id)
        old_owner_membership = ConversationMember.objects.get(
            conversation=self.group, user=self.owner
        )
        self.assertEqual(old_owner_membership.role, ConversationMember.Role.ADMIN)

        leave = self.client.post(
            f"/api/conversations/{self.group.conversation_id}/leave/",
            headers={"If-Match": '"2"'},
        )
        self.assertEqual(leave.status_code, 200)
        old_owner_membership.refresh_from_db()
        self.assertFalse(old_owner_membership.is_active)

    def test_archived_group_remains_readable_but_rejects_new_messages(self):
        archived = self.client.post(
            f"/api/conversations/{self.group.conversation_id}/archive/",
            headers={"If-Match": '"1"'},
        )
        self.assertEqual(archived.status_code, 200)
        self.assertTrue(archived.json()["is_archived"])
        conversation, history = ChatService().load_history(
            self.group.conversation_id, self.owner.user_id
        )
        self.assertEqual(conversation.conversation_id, self.group.conversation_id)
        self.assertEqual(history, [])
        with self.assertRaises(ServiceError):
            ChatService().send_message(
                self.owner.user_id,
                self.group.conversation_id,
                str(uuid.uuid4()),
                "not allowed",
            )
