import uuid

from django.db import models


class User(models.Model):
    class PresenceStatus(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"

    class Sex(models.TextChoices):
        FEMALE = "female", "Female"
        MALE = "male", "Male"

    user_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="user_id",
    )
    username = models.CharField(
        max_length=100,
        unique=True,
        db_column="username",
    )
    avatar = models.FileField(
        upload_to="avatars/",
        null=True,
        blank=True,
        db_column="avatar",
    )
    status = models.CharField(
        max_length=10,
        choices=PresenceStatus.choices,
        default=PresenceStatus.OFFLINE,
        db_column="status",
    )
    short_bio = models.CharField(
        max_length=160,
        blank=True,
        db_column="short_bio",
    )
    bio = models.TextField(blank=True, db_column="bio")
    sex = models.CharField(
        max_length=10,
        choices=Sex.choices,
        blank=True,
        db_column="sex",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column="created_at",
    )
    friends = models.ManyToManyField(
        "self",
        through="UserFriend",
        symmetrical=False,
        related_name="friend_of",
    )

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.username


class Invitation(models.Model):
    class InvitationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPT = "ACCEPT", "Accepted"
        REJECT = "REJECT", "Rejected"

    invitation_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="id",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="sender_id",
        related_name="sent_invitations",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="received_invitations",
    )
    status = models.CharField(
        max_length=10,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_column="status",
    )
    send_time = models.DateTimeField(auto_now_add=True, db_column="send_time")

    class Meta:
        db_table = "invitation"
        indexes = [
            models.Index(fields=["user", "status"], name="idx_invitation_user_status"),
        ]

    def __str__(self):
        return f"{self.sender} -> {self.user}: {self.status}"


class UserFriend(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="friend_links",
    )
    friend = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="friend_id",
        related_name="friend_links_received",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column="created_at")

    class Meta:
        db_table = "user_friends"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "friend"],
                name="uq_user_friend",
            ),
            models.CheckConstraint(
                condition=~models.Q(user=models.F("friend")),
                name="ck_user_friend_not_self",
            ),
        ]
        indexes = [
            models.Index(fields=["user"], name="idx_user_friend_user"),
            models.Index(fields=["friend"], name="idx_user_friend_friend"),
        ]

    def __str__(self):
        return f"{self.user} -> {self.friend}"


class Conversation(models.Model):
    class ConversationType(models.TextChoices):
        PRIVATE = "PRIVATE", "Private"
        GROUP = "GROUP", "Group"

    conversation_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="conversation_id",
    )
    name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_column="name",
    )
    conversation_type = models.CharField(
        max_length=10,
        choices=ConversationType.choices,
        db_column="conversation_type",
    )
    last_seq = models.BigIntegerField(default=0, db_column="last_seq")
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column="created_at",
    )

    class Meta:
        db_table = "conversations"

    def __str__(self):
        return self.name or str(self.conversation_id)


class ConversationMember(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        db_column="conversation_id",
        related_name="members",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="chat_conversations",
    )
    joined_at = models.DateTimeField(
        auto_now_add=True,
        db_column="joined_at",
    )

    class Meta:
        db_table = "conversation_members"
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "user"],
                name="uq_conversation_member",
            )
        ]
        indexes = [
            models.Index(fields=["user"], name="idx_member_user"),
        ]

    def __str__(self):
        return f"{self.user} in {self.conversation}"


class RoomInvitation(models.Model):
    class InvitationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPT = "ACCEPT", "Accepted"
        REJECT = "REJECT", "Rejected"

    invitation_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="id",
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        db_column="conversation_id",
        related_name="room_invitations",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="sender_id",
        related_name="sent_room_invitations",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="received_room_invitations",
    )
    status = models.CharField(
        max_length=10,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        db_column="status",
    )
    send_time = models.DateTimeField(auto_now_add=True, db_column="send_time")

    class Meta:
        db_table = "room_invitations"
        indexes = [
            models.Index(
                fields=["user", "status", "send_time"],
                name="idx_room_inv_user_status_time",
            ),
            models.Index(fields=["sender", "status"], name="idx_room_inv_sender_status"),
        ]

    def __str__(self):
        return f"{self.sender} -> {self.user} in {self.conversation}: {self.status}"


class Message(models.Model):
    message_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_column="message_id",
    )
    client_message_id = models.CharField(
        max_length=36,
        db_column="client_message_id",
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        db_column="conversation_id",
        related_name="messages",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="sender_id",
        related_name="sent_messages",
    )
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="reply_to_message_id",
        related_name="replies",
    )
    content = models.TextField(db_column="content")
    seq = models.BigIntegerField(db_column="seq")
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_column="created_at",
    )

    class Meta:
        db_table = "messages"
        ordering = ["conversation", "seq"]
        constraints = [
            models.UniqueConstraint(
                fields=["sender", "client_message_id"],
                name="uk_sender_client_message",
            ),
            models.UniqueConstraint(
                fields=["conversation", "seq"],
                name="uk_conversation_seq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["conversation", "seq"],
                name="idx_message_conversation_seq",
            ),
            models.Index(fields=["sender"], name="idx_message_sender"),
        ]

    def __str__(self):
        return f"{self.sender}: {self.content[:40]}"


class MessageReceipt(models.Model):
    class ReceiptStatus(models.TextChoices):
        DELIVERED = "DELIVERED", "Delivered"
        READ = "READ", "Read"

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        db_column="message_id",
        related_name="receipts",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
        related_name="message_receipts",
    )
    status = models.CharField(
        max_length=10,
        choices=ReceiptStatus.choices,
        db_column="status",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_column="updated_at",
    )

    class Meta:
        db_table = "message_receipts"
        constraints = [
            models.UniqueConstraint(
                fields=["message", "user"],
                name="uq_message_receipt",
            )
        ]

    def __str__(self):
        return f"{self.message} -> {self.user}: {self.status}"