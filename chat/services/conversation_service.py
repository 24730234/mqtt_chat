from ..db_connection import DatabaseConnection
from ..models import Conversation, User
from ..repositories import ConversationRepository, UserRepository
from .errors import NotFoundError, PermissionError, ServiceError
from .user_service import UserService


class ConversationService:
    MAX_HISTORY_LIMIT = 100

    def __init__(self, db=None, users=None, conversations=None):
        self.db = db or DatabaseConnection()
        self.users = users or UserRepository()
        self.conversations = conversations or ConversationRepository()

    @staticmethod
    def _parse_id(value):
        return UserService._parse_id(value)

    def _get_user(self, value):
        user_id = self._parse_id(value)
        user = self.users.get(user_id) if user_id else None
        if user is None:
            raise NotFoundError("user not found")
        return user

    def create_conversation(
        self,
        creator_id,
        conversation_type,
        username=None,
        usernames=None,
        name=None,
    ):
        creator = self._get_user(creator_id)
        if conversation_type not in Conversation.ConversationType.values:
            raise ServiceError("type must be PRIVATE or GROUP")
        if name is not None:
            if not isinstance(name, str) or not name.strip():
                raise ServiceError("name must be a non-empty string")
            name = name.strip()
            if len(name) > 255:
                raise ServiceError("name must be 255 characters or fewer")

        if conversation_type == Conversation.ConversationType.PRIVATE:
            if not isinstance(username, str) or not username.strip():
                raise ServiceError("username is required for a private conversation")
            other_user = self.users.get_by_username(username.strip())
            if other_user is None:
                raise NotFoundError("user not found")
            if other_user == creator:
                raise ServiceError("cannot create a private conversation with yourself")
            with self.db.transaction():
                list(
                    User.objects.select_for_update()
                    .filter(user_id__in=[creator.user_id, other_user.user_id])
                    .order_by("user_id")
                )
                conversation = self.conversations.get_private_between(
                    creator, other_user
                )
                if conversation is None:
                    conversation = self.conversations.create(
                        conversation_type,
                        [creator, other_user],
                    )
            return conversation

        if usernames is None:
            usernames = []
        if not isinstance(usernames, list) or any(
            not isinstance(item, str) or not item.strip() for item in usernames
        ):
            raise ServiceError("usernames must be a list of non-empty usernames")

        requested_names = dict.fromkeys(username.strip() for username in usernames)
        members = [creator]
        missing_names = []
        for requested_name in requested_names:
            user = self.users.get_by_username(requested_name)
            if user is None:
                missing_names.append(requested_name)
            elif user != creator:
                members.append(user)
        if missing_names:
            raise NotFoundError(f"users not found: {', '.join(missing_names)}")
        if len(members) < 2:
            raise ServiceError("a group conversation requires at least two users")

        with self.db.transaction():
            return self.conversations.create(
                conversation_type,
                members,
                name=name,
            )

    def load_history(self, conversation_id, user_id, before_seq=None, limit=50):
        conversation = self._get_member_conversation(conversation_id, user_id)
        before_seq, limit = self._pagination_values(before_seq, limit)
        messages = list(
            self.conversations.messages(
                conversation,
                before_seq=before_seq,
                limit=limit,
            )
        )
        return conversation, list(reversed(messages))

    def search_messages(
        self, conversation_id, user_id, query, before_seq=None, limit=50
    ):
        if not isinstance(query, str) or not query.strip():
            raise ServiceError("q must be a non-empty string")
        conversation = self._get_member_conversation(conversation_id, user_id)
        before_seq, limit = self._pagination_values(before_seq, limit)
        messages = list(
            self.conversations.search_messages(
                conversation,
                query.strip(),
                before_seq=before_seq,
                limit=limit,
            )
        )
        return conversation, list(reversed(messages))

    def _get_member_conversation(self, conversation_id, user_id):
        parsed_conversation_id = self._parse_id(conversation_id)
        conversation = (
            self.conversations.get(parsed_conversation_id)
            if parsed_conversation_id
            else None
        )
        if conversation is None:
            raise NotFoundError("conversation not found")
        user = self._get_user(user_id)
        if not self.conversations.is_member(conversation, user):
            raise PermissionError("user is not a member of this conversation")
        return conversation

    @classmethod
    def _pagination_values(cls, before_seq, limit):
        if before_seq is not None:
            try:
                before_seq = int(before_seq)
            except (TypeError, ValueError) as exc:
                raise ServiceError("before_seq must be a positive integer") from exc
            if before_seq < 1:
                raise ServiceError("before_seq must be a positive integer")
        try:
            limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ServiceError("limit must be a positive integer") from exc
        if limit < 1:
            raise ServiceError("limit must be a positive integer")
        limit = min(limit, cls.MAX_HISTORY_LIMIT)
        return before_seq, limit
