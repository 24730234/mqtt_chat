from ..models import Message, MessageReceipt


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

    def mark_read(self, conversation, user, message_ids):
        read_ids = []
        messages = Message.objects.filter(
            conversation=conversation,
            message_id__in=message_ids,
        ).exclude(sender=user)
        for message in messages:
            receipt, created = MessageReceipt.objects.get_or_create(
                message=message,
                user=user,
                defaults={"status": MessageReceipt.ReceiptStatus.READ},
            )
            if created:
                read_ids.append(str(message.message_id))
            elif receipt.status != MessageReceipt.ReceiptStatus.READ:
                receipt.status = MessageReceipt.ReceiptStatus.READ
                receipt.save(update_fields=["status", "updated_at"])
                read_ids.append(str(message.message_id))
        return read_ids
