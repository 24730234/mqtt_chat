from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, Subquery

from ..models import Conversation, ConversationMember, Message, MessageReceipt


class ConversationRepository:
    def get(self, conversation_id):
        return Conversation.objects.filter(conversation_id=conversation_id).first()

    def get_for_update(self, conversation_id):
        return (
            Conversation.objects.select_for_update()
            .filter(conversation_id=conversation_id)
            .first()
        )

    def list_for_user(self, user):
        latest_message_at = (
            Message.objects.filter(conversation_id=OuterRef("pk"))
            .order_by("-created_at", "-seq")
            .values("created_at")[:1]
        )
        conversations = list(
            Conversation.objects.filter(members__user=user)
            .annotate(last_message_at=Subquery(latest_message_at))
            .order_by(F("last_message_at").desc(nulls_last=True), "-created_at")
            .prefetch_related(
                Prefetch(
                    "members",
                    queryset=ConversationMember.objects.select_related("user").order_by(
                        "user__username"
                    ),
                )
            )
        )
        if not conversations:
            return conversations

        conversation_ids = [
            conversation.conversation_id for conversation in conversations
        ]
        read_receipts = MessageReceipt.objects.filter(
            message_id=OuterRef("message_id"),
            user=user,
            status=MessageReceipt.ReceiptStatus.READ,
        )
        unread_counts = (
            Message.objects.filter(conversation_id__in=conversation_ids)
            .exclude(sender=user)
            .annotate(is_read=Exists(read_receipts))
            .filter(is_read=False)
            .values("conversation_id")
            .annotate(count=Count("message_id"))
        )
        unread_count_by_conversation = {
            row["conversation_id"]: row["count"] for row in unread_counts
        }
        for conversation in conversations:
            conversation.unread_count = unread_count_by_conversation.get(
                conversation.conversation_id, 0
            )

        latest_messages = (
            Message.objects.filter(conversation_id__in=conversation_ids)
            .select_related("sender")
            .prefetch_related(
                Prefetch(
                    "receipts",
                    queryset=MessageReceipt.objects.filter(
                        status=MessageReceipt.ReceiptStatus.READ
                    ).select_related("user"),
                )
            )
            .order_by("conversation_id", "-created_at", "-seq")
        )
        last_message_by_conversation = {}
        for message in latest_messages:
            last_message_by_conversation.setdefault(
                message.conversation_id, message
            )
        for conversation in conversations:
            conversation.last_message = last_message_by_conversation.get(
                conversation.conversation_id
            )
        return conversations

    def save_last_seq(self, conversation):
        conversation.save(update_fields=["last_seq"])

    def get_private_between(self, first, second):
        member_ids = [first.user_id, second.user_id]
        return (
            Conversation.objects.filter(
                conversation_type=Conversation.ConversationType.PRIVATE,
            )
            .annotate(
                member_count=Count("members", distinct=True),
                matching_member_count=Count(
                    "members",
                    filter=Q(members__user_id__in=member_ids),
                    distinct=True,
                ),
            )
            .filter(member_count=2, matching_member_count=2)
            .first()
        )

    def create(self, conversation_type, users, name=None):
        conversation = Conversation.objects.create(
            conversation_type=conversation_type,
            name=name,
        )
        ConversationMember.objects.bulk_create(
            [
                ConversationMember(conversation=conversation, user=user)
                for user in users
            ]
        )
        return conversation

    def is_member(self, conversation, user):
        return ConversationMember.objects.filter(
            conversation=conversation,
            user=user,
        ).exists()

    def messages(self, conversation, before_seq=None, limit=50):
        messages = (
            conversation.messages.select_related("sender", "reply_to")
            .prefetch_related(
                Prefetch(
                    "receipts",
                    queryset=MessageReceipt.objects.filter(
                        status=MessageReceipt.ReceiptStatus.READ
                    ).select_related("user"),
                )
            )
        )
        if before_seq is not None:
            messages = messages.filter(seq__lt=before_seq)
        return messages.order_by("-seq")[:limit]

    def search_messages(self, conversation, query, before_seq=None, limit=50):
        messages = (
            conversation.messages.select_related("sender", "reply_to")
            .prefetch_related(
                Prefetch(
                    "receipts",
                    queryset=MessageReceipt.objects.filter(
                        status=MessageReceipt.ReceiptStatus.READ
                    ).select_related("user"),
                )
            )
            .filter(content__icontains=query)
        )
        if before_seq is not None:
            messages = messages.filter(seq__lt=before_seq)
        return messages.order_by("-seq")[:limit]
