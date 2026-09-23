import uuid

from django.db import models
from django.contrib.auth.models import User


class Conversation(models.Model):

    TYPE_CHOICES = [
        ("PRIVATE", "Private"),
        ("GROUP", "Group"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    name = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    conversation_type = models.CharField(
        max_length=10,
        choices=TYPE_CHOICES
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name or str(self.id)


class ConversationMember(models.Model):

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="members"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    joined_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "conversation",
                    "user"
                ],
                name="unique_conversation_member"
            )
        ]

class Message(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    client_message_id = models.UUIDField()

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages"
    )

    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    content = models.TextField()

    seq = models.BigIntegerField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        ordering = ["seq"]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "sender",
                    "client_message_id"
                ],
                name="unique_client_message"
            ),

            models.UniqueConstraint(
                fields=[
                    "conversation",
                    "seq"
                ],
                name="unique_conversation_sequence"
            )
        ]

class MessageReceipt(models.Model):

    STATUS_CHOICES = [
        ("DELIVERED", "Delivered"),
        ("READ", "Read"),
    ]

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="receipts"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "message",
                    "user"
                ],
                name="unique_message_receipt"
            )
        ]