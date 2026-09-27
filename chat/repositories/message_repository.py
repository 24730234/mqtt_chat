from ..models import Message


class MessageRepository:
    def get_by_sender_and_client_id(self, sender, client_message_id):
        return (
            Message.objects.select_related("conversation", "reply_to")
            .filter(sender=sender, client_message_id=client_message_id)
            .first()
        )

    def get(self, message_id):
        return (
            Message.objects.select_related("conversation")
            .filter(message_id=message_id)
            .first()
        )

    def create(self, **fields):
        return Message.objects.create(**fields)
