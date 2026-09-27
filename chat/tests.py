from django.test import TestCase

import json
import tempfile
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, TransactionTestCase, override_settings

from .models import (
    Conversation,
    ConversationMember,
    Message,
    User,
)
from .mqtt_messages import (
    CLIENT_EVENT_TOPIC,
    CONVERSATION_MESSAGE_TOPIC,
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
        Message.objects.create(
            client_message_id="history-2",
            conversation=conversation,
            sender=self.sarah,
            content="second",
            seq=2,
            reply_to=first,
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

        forbidden = self.client.get(
            f"/api/conversations/{conversation.conversation_id}/messages/",
            {"user_id": str(self.kevin.user_id)},
        )
        self.assertEqual(forbidden.status_code, 403)


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
