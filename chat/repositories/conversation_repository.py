from django.db.models import Count, Q

from ..models import Conversation, ConversationMember


class ConversationRepository:
    def get(self, conversation_id):
        return Conversation.objects.filter(conversation_id=conversation_id).first()

    def get_for_update(self, conversation_id):
        return (
            Conversation.objects.select_for_update()
            .filter(conversation_id=conversation_id)
            .first()
        )

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
        messages = conversation.messages.select_related("sender", "reply_to")
        if before_seq is not None:
            messages = messages.filter(seq__lt=before_seq)
        return messages.order_by("-seq")[:limit]

    def search_messages(self, conversation, query, before_seq=None, limit=50):
        messages = conversation.messages.select_related("sender", "reply_to").filter(
            content__icontains=query
        )
        if before_seq is not None:
            messages = messages.filter(seq__lt=before_seq)
        return messages.order_by("-seq")[:limit]
