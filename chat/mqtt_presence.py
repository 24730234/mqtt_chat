import logging
import uuid

import paho.mqtt.client as mqtt
from django.db import DatabaseError, close_old_connections

from .models import User
from .repositories import UserRepository


logger = logging.getLogger(__name__)
PRESENCE_TOPIC = "chat/users/+/status"


class PresenceSubscriber:
    def __init__(self, client=None, users=None):
        self.users = users or UserRepository()
        self.client = client or mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="mqtt-chat-presence",
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            logger.error("MQTT presence subscriber connection failed: %s", reason_code)
            return
        client.subscribe(PRESENCE_TOPIC, qos=1)
        logger.info("Subscribed to MQTT presence topic %s", PRESENCE_TOPIC)

    def on_message(self, client, userdata, message):
        topic_parts = message.topic.split("/")
        if (
            len(topic_parts) != 4
            or topic_parts[:2] != ["chat", "users"]
            or topic_parts[3] != "status"
        ):
            logger.warning("Ignoring malformed MQTT presence topic: %s", message.topic)
            return
        try:
            user_id = uuid.UUID(topic_parts[2])
            status = message.payload.decode("utf-8").strip()
        except (ValueError, UnicodeDecodeError):
            logger.warning("Ignoring malformed MQTT presence message on %s", message.topic)
            return
        if status not in User.PresenceStatus.values:
            logger.warning("Ignoring invalid presence status on %s", message.topic)
            return

        close_old_connections()
        try:
            if not self.users.update_status(user_id, status):
                logger.warning("Presence update references unknown user %s", user_id)
        except DatabaseError:
            logger.exception("Could not save MQTT presence for user %s", user_id)
        finally:
            close_old_connections()

    def run(self, host, port, username=None, password=None):
        if username:
            self.client.username_pw_set(username, password)
        self.client.connect(host, port, keepalive=60)
        self.client.loop_forever()
