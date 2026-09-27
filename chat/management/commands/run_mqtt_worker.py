import os

from django.core.management.base import BaseCommand

from chat.mqtt_messages import MessageCommandSubscriber


class Command(BaseCommand):
    help = "Subscribe to MQTT send-message commands and persist messages."

    def handle(self, *args, **options):
        host = os.environ.get("MQTT_HOST", "127.0.0.1")
        port = int(os.environ.get("MQTT_PORT", "1883"))
        username = os.environ.get("MQTT_USERNAME")
        password = os.environ.get("MQTT_PASSWORD")

        self.stdout.write(f"Connecting MQTT message worker to {host}:{port}")
        MessageCommandSubscriber().run(
            host,
            port,
            username=username,
            password=password,
        )
