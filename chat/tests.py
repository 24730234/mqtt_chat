from django.test import TestCase

import json
import tempfile
import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, TransactionTestCase, override_settings

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
    MessageCommandSubscriber,
)
from .mqtt_presence import PresenceSubscriber


class UserAvatarTests(TestCase):
    def setUp(self):
        media_directory = tempfile.TemporaryDirectory()
        self.addCleanup(media_directory.cleanup)
        media_settings = override_settings(MEDIA_ROOT=media_directory.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.client = Client()
        self.user = User.objects.create(username="avatar-user")
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
            "/api/users/",
            data=json.dumps(
                {
                    "username": "profile-user",
                    "short_bio": "IoT learner",
                    "bio": "Building chat apps.",
                    "sex": "female",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        user_id = response.json()["user_id"]
        self.assertEqual(response.json()["status"], User.PresenceStatus.OFFLINE)
        self.assertEqual(response.json()["short_bio"], "IoT learner")
        self.assertEqual(response.json()["sex"], "female")

        response = self.client.patch(
            f"/api/users/{user_id}/",
            data=json.dumps({"bio": "Updated bio", "status": "online", "sex": "male"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["bio"], "Updated bio")
        self.assertEqual(response.json()["status"], "online")
        self.assertEqual(response.json()["sex"], "male")
        self.assertEqual(response.json()["short_bio"], "IoT learner")

    def test_rejects_invalid_profile_values(self):
        response = self.client.post(
            "/api/users/",
            data=json.dumps({"username": "bad-user", "sex": "other"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="bad-user").exists())


class FriendsApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(username="friend-list-owner")
        self.friend = User.objects.create(username="friend-entry")
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

    def post_json(self, url, body):
        return self.client.post(
            url,
            data=json.dumps(body),
            content_type="application/json",
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
        self.assertEqual(
            set(
                ConversationMember.objects.filter(
                    conversation_id=response.json()["conversation_id"]
                ).values_list("user_id", flat=True)
            ),
            {self.alex.user_id, self.sarah.user_id, self.kevin.user_id},
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
        self.assertEqual(response.status_code, 404)

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
        )
        ConversationMember.objects.create(conversation=group, user=self.alex)
        response = self.post_json(
            "/api/room-invitations/",
            {
                "sender_id": str(self.alex.user_id),
                "user_id": str(self.sarah.user_id),
                "conversation_id": str(group.conversation_id),
            },
        )
        self.assertEqual(response.status_code, 201)
        invitation_id = response.json()["invitation_id"]

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
            {"user_id": str(self.sarah.user_id), "status": "ACCEPT"},
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
            conversation_type=Conversation.ConversationType.GROUP
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
        rejected = self.post_json(
            f"/api/room-invitations/{invitation.invitation_id}/respond/",
            {"user_id": str(self.sarah.user_id), "status": "REJECT"},
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
        self.assertEqual(self.client.publish.call_count, 2)

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
        self.assertEqual(self.client.publish.call_count, 3)
        retry_ack = json.loads(self.client.publish.call_args_list[2].args[1])
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
