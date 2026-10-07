import uuid

from django.db import IntegrityError

from ..db_connection import DatabaseConnection
from ..repositories import (
    ConversationRepository,
    MessageRepository,
    UserRepository,
)
from .errors import ConflictError, NotFoundError, PermissionError, ServiceError
from .user_service import UserService


class MessageService:
    MAX_READ_BATCH = 100

    def __init__(self, db=None, users=None, conversations=None, messages=None):
        self.db = db or DatabaseConnection()
        self.users = users or UserRepository()
        self.conversations = conversations or ConversationRepository()
        self.messages = messages or MessageRepository()

    @staticmethod
    def _parse_uuid(value, field):
        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ServiceError(f"{field} must be a valid UUID") from exc

    def _get_sender(self, sender_id):
        parsed_sender_id = UserService._parse_id(sender_id)
        sender = self.users.get(parsed_sender_id) if parsed_sender_id else None
        if sender is None:
            raise NotFoundError("sender not found")
        return sender

    @staticmethod
    def _check_duplicate(
        existing,
        conversation_id,
        content,
        reply_to_id,
    ):
        if (
            existing.conversation_id != conversation_id
            or existing.content != content
            or existing.reply_to_id != reply_to_id
        ):
            raise ConflictError(
                "client_message_id was already used for a different message"
            )
        return existing, False

    def send_message(
        self,
        sender_id,
        conversation_id,
        client_message_id,
        content,
        reply_to_message_id=None,
    ):
        sender = self._get_sender(sender_id)
        conversation_id = self._parse_uuid(conversation_id, "conversation_id")
        client_message_id = str(
            self._parse_uuid(client_message_id, "client_message_id")
        )
        reply_to_id = (
            self._parse_uuid(reply_to_message_id, "reply_to_message_id")
            if reply_to_message_id is not None
            else None
        )
        if not isinstance(content, str) or not content.strip():
            raise ServiceError("content must be a non-empty string")

        conversation = self.conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("conversation not found")
        if not self.conversations.is_member(conversation, sender):
            raise PermissionError("sender is not a member of this conversation")

        existing = self.messages.get_by_sender_and_client_id(
            sender, client_message_id
        )
        if existing is not None:
            return self._check_duplicate(
                existing,
                conversation_id,
                content,
                reply_to_id,
            )

        try:
            with self.db.transaction():
                conversation = self.conversations.get_for_update(conversation_id)
                if conversation is None:
                    raise NotFoundError("conversation not found")
                if not self.conversations.is_member(conversation, sender):
                    raise PermissionError(
                        "sender is not a member of this conversation"
                    )

                # Recheck under the conversation lock before allocating a sequence.
                existing = self.messages.get_by_sender_and_client_id(
                    sender, client_message_id
                )
                if existing is not None:
                    return self._check_duplicate(
                        existing,
                        conversation_id,
                        content,
                        reply_to_id,
                    )

                reply_to = None
                if reply_to_id is not None:
                    reply_to = self.messages.get(reply_to_id)
                    if reply_to is None or reply_to.conversation_id != conversation_id:
                        raise NotFoundError(
                            "reply target not found in this conversation"
                        )

                conversation.last_seq += 1
                self.conversations.save_last_seq(conversation)
                message = self.messages.create(
                    conversation=conversation,
                    sender=sender,
                    client_message_id=client_message_id,
                    content=content,
                    seq=conversation.last_seq,
                    reply_to=reply_to,
                )
            return message, True
        except IntegrityError:
            existing = self.messages.get_by_sender_and_client_id(
                sender, client_message_id
            )
            if existing is None:
                raise
            return self._check_duplicate(
                existing,
                conversation_id,
                content,
                reply_to_id,
            )

    def mark_messages_read(self, user_id, conversation_id, message_ids):
        user = self._get_sender(user_id)
        conversation_id = self._parse_uuid(conversation_id, "conversation_id")
        if not isinstance(message_ids, list) or not message_ids:
            raise ServiceError("message_ids must be a non-empty list")
        if len(message_ids) > self.MAX_READ_BATCH:
            raise ServiceError(
                f"message_ids must contain at most {self.MAX_READ_BATCH} items"
            )
        parsed_ids = list(
            dict.fromkeys(
                self._parse_uuid(message_id, "message_id")
                for message_id in message_ids
            )
        )

        conversation = self.conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("conversation not found")
        if not self.conversations.is_member(conversation, user):
            raise PermissionError("user is not a member of this conversation")

        with self.db.transaction():
            read_ids = self.messages.mark_read(conversation, user, parsed_ids)
        return conversation, user, read_ids
