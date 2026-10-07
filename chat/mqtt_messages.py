import json
import logging
import uuid

import paho.mqtt.client as mqtt
from django.db import DatabaseError, close_old_connections

from .services import ChatService, ServiceError


logger = logging.getLogger(__name__)
SEND_MESSAGE_TOPIC = "chat/client/+/command/send"
READ_MESSAGES_TOPIC = "chat/client/+/command/read"
CLIENT_EVENT_TOPIC = "chat/client/{user_id}/event/{event}"
CONVERSATION_MESSAGE_TOPIC = "chat/conversations/{conversation_id}/event/message_created"
CONVERSATION_READ_TOPIC = "chat/conversations/{conversation_id}/event/message_read"


class MessageCommandSubscriber:
    def __init__(self, client=None, chat_service=None):
        self.chat_service = chat_service or ChatService()
        self.client = client or mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="mqtt-chat-messages",
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            logger.error("MQTT message subscriber connection failed: %s", reason_code)
            return
        client.subscribe(SEND_MESSAGE_TOPIC, qos=1)
        client.subscribe(READ_MESSAGES_TOPIC, qos=1)
        logger.info("Subscribed to MQTT message command topics")

    @staticmethod
    def _publish(client, topic, payload):
        result = client.publish(topic, json.dumps(payload), qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error("Could not publish MQTT event to %s: rc=%s", topic, result.rc)

    def _publish_error(self, client, user_id, client_message_id, reason):
        self._publish(
            client,
            CLIENT_EVENT_TOPIC.format(user_id=user_id, event="error"),
            {
                "type": "ERROR",
                "client_message_id": client_message_id,
                "error": reason,
            },
        )

    def on_message(self, client, userdata, message):
        topic_parts = message.topic.split("/")
        is_send = topic_parts[3:] == ["command", "send"]
        is_read = topic_parts[3:] == ["command", "read"]
        if (
            len(topic_parts) != 5
            or topic_parts[:2] != ["chat", "client"]
            or not (is_send or is_read)
        ):
            logger.warning("Ignoring malformed MQTT message topic: %s", message.topic)
            return

        try:
            sender_id = uuid.UUID(topic_parts[2])
        except ValueError:
            logger.warning("Ignoring MQTT command with invalid user ID")
            return

        if is_read:
            self._handle_read(client, sender_id, message)
            return

        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._publish_error(client, sender_id, None, "payload must be valid JSON")
            return
        if not isinstance(payload, dict):
            self._publish_error(client, sender_id, None, "payload must be a JSON object")
            return

        client_message_id = payload.get("client_message_id")
        if not isinstance(client_message_id, str):
            client_message_id = None
        if "seq" in payload:
            self._publish_error(
                client,
                sender_id,
                client_message_id,
                "seq is assigned by the server and must not be provided",
            )
            return

        close_old_connections()
        try:
            saved_message, created = self.chat_service.send_message(
                sender_id=sender_id,
                conversation_id=payload.get("conversation_id"),
                client_message_id=client_message_id,
                content=payload.get("content"),
                reply_to_message_id=payload.get("reply_to_message_id"),
            )
        except ServiceError as error:
            error_reason = str(error)
            saved_message = None
            created = False
        except DatabaseError:
            logger.exception("Could not persist MQTT message from user %s", sender_id)
            error_reason = "message could not be saved"
            saved_message = None
            created = False
        else:
            error_reason = None
        finally:
            close_old_connections()

        if error_reason is not None:
            self._publish_error(client, sender_id, client_message_id, error_reason)
            return

        accepted = {
            "type": "MESSAGE_ACCEPTED",
            "client_message_id": saved_message.client_message_id,
            "message_id": str(saved_message.message_id),
            "conversation_id": str(saved_message.conversation_id),
            "seq": saved_message.seq,
            "created_at": saved_message.created_at.isoformat(),
            "duplicate": not created,
        }
        self._publish(
            client,
            CLIENT_EVENT_TOPIC.format(user_id=sender_id, event="message_accepted"),
            accepted,
        )

        if created:
            self._publish(
                client,
                CONVERSATION_MESSAGE_TOPIC.format(
                    conversation_id=saved_message.conversation_id
                ),
                {
                    **accepted,
                    "type": "MESSAGE_CREATED",
                    "sender_id": str(sender_id),
                    "content": saved_message.content,
                    "reply_to_message_id": (
                        str(saved_message.reply_to_id)
                        if saved_message.reply_to_id
                        else None
                    ),
                },
            )

    def _handle_read(self, client, user_id, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._publish_error(client, user_id, None, "payload must be valid JSON")
            return
        if not isinstance(payload, dict):
            self._publish_error(
                client, user_id, None, "payload must be a JSON object"
            )
            return

        close_old_connections()
        try:
            conversation, reader, read_ids = self.chat_service.mark_messages_read(
                user_id=user_id,
                conversation_id=payload.get("conversation_id"),
                message_ids=payload.get("message_ids"),
            )
        except ServiceError as error:
            error_reason = str(error)
            conversation = None
            reader = None
            read_ids = []
        except DatabaseError:
            logger.exception("Could not persist read receipts for user %s", user_id)
            error_reason = "read receipts could not be saved"
            conversation = None
            reader = None
            read_ids = []
        else:
            error_reason = None
        finally:
            close_old_connections()

        if error_reason is not None:
            self._publish_error(client, user_id, None, error_reason)
            return
        if read_ids:
            self._publish(
                client,
                CONVERSATION_READ_TOPIC.format(
                    conversation_id=conversation.conversation_id
                ),
                {
                    "type": "MESSAGE_READ",
                    "conversation_id": str(conversation.conversation_id),
                    "reader_id": str(reader.user_id),
                    "message_ids": read_ids,
                },
            )

    def run(self, host, port, username=None, password=None):
        if username:
            self.client.username_pw_set(username, password)
        self.client.connect(host, port, keepalive=60)
        self.client.loop_forever()
