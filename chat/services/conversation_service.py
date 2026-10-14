from django.utils import timezone

from ..db_connection import DatabaseConnection
from ..models import (
    Conversation,
    ConversationMember,
    RoomInvitation,
    User,
)
from ..repositories import (
    ConversationRepository,
    RoomInvitationRepository,
    UserRepository,
)
from .errors import (
    ConflictError,
    NotFoundError,
    PermissionError,
    PreconditionFailed,
    PreconditionRequired,
    ServiceError,
)
from .user_service import UserService


class ConversationService:
    MAX_HISTORY_LIMIT = 100

    def __init__(
        self, db=None, users=None, conversations=None, room_invitations=None
    ):
        self.db = db or DatabaseConnection()
        self.users = users or UserRepository()
        self.conversations = conversations or ConversationRepository()
        self.room_invitations = room_invitations or RoomInvitationRepository()

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
            if other_user.auth_user_id is None or not other_user.auth_user.is_active:
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
        invitees = []
        missing_names = []
        for requested_name in requested_names:
            user = self.users.get_by_username(requested_name)
            if user is None:
                missing_names.append(requested_name)
            elif user != creator:
                if user.auth_user_id is None or not user.auth_user.is_active:
                    missing_names.append(requested_name)
                else:
                    invitees.append(user)
        if missing_names:
            raise NotFoundError(f"users not found: {', '.join(missing_names)}")

        with self.db.transaction():
            conversation = self.conversations.create(
                conversation_type,
                [creator],
                name=name,
                owner=creator,
            )
            for invitee in invitees:
                self.room_invitations.create(conversation, creator, invitee)
            if invitees:
                conversation.version += len(invitees)
                conversation.save(update_fields=["version"])
            return conversation

    def list_conversations(self, user_id):
        user = self._get_user(user_id)
        return self.conversations.list_for_user(user)

    def send_room_invitation(
        self, sender_id, recipient_id, conversation_id, expected_version=None
    ):
        sender = self._get_user(sender_id)
        recipient = self._get_user(recipient_id)
        parsed_conversation_id = self._parse_id(conversation_id)
        if parsed_conversation_id is None:
            raise NotFoundError("conversation not found")
        if sender == recipient:
            raise ServiceError("cannot invite yourself to a conversation")
        if recipient.auth_user_id is None or not recipient.auth_user.is_active:
            raise NotFoundError("user not found")

        with self.db.transaction():
            conversation = self.conversations.get_for_update(parsed_conversation_id)
            if conversation is None:
                raise NotFoundError("conversation not found")
            if conversation.conversation_type != Conversation.ConversationType.GROUP:
                raise ServiceError("room invitations require a group conversation")
            self._check_version(conversation, expected_version)
            self._require_group_admin(conversation, sender)
            if conversation.is_archived:
                raise ConflictError("conversation is archived")
            if self.conversations.is_member(conversation, recipient):
                raise ConflictError("user is already a member of this conversation")
            if self.room_invitations.has_pending(conversation, recipient):
                raise ConflictError("a pending room invitation already exists")
            invitation = self.room_invitations.create(conversation, sender, recipient)
            conversation.version += 1
            conversation.save(update_fields=["version"])
            return invitation

    def list_room_invitations(self, user_id):
        return self.room_invitations.list_for_user(self._get_user(user_id))

    def respond_to_room_invitation(
        self, invitation_id, responder_id, status, expected_version=None
    ):
        parsed_invitation_id = self._parse_id(invitation_id)
        responder = self._get_user(responder_id)
        if status not in (
            RoomInvitation.InvitationStatus.ACCEPT,
            RoomInvitation.InvitationStatus.REJECT,
        ):
            raise ServiceError("status must be ACCEPT or REJECT")

        initial = RoomInvitation.objects.filter(
            invitation_id=parsed_invitation_id
        ).only("conversation_id").first()
        if initial is None:
            raise NotFoundError("room invitation not found")
        invalidated = False
        result = None
        with self.db.transaction():
            conversation = self.conversations.get_for_update(initial.conversation_id)
            invitation = self.room_invitations.get_for_update(parsed_invitation_id)
            if conversation is None or invitation is None:
                raise NotFoundError("room invitation not found")
            self._check_version(conversation, expected_version)
            if responder != invitation.user:
                raise PermissionError("only the recipient can respond")
            if invitation.status != RoomInvitation.InvitationStatus.PENDING:
                raise ConflictError("invitation has already been handled")
            if status == RoomInvitation.InvitationStatus.ACCEPT:
                if conversation.is_archived or not self._can_invite(
                    conversation, invitation.sender
                ):
                    self.room_invitations.save_status(
                        invitation, RoomInvitation.InvitationStatus.CANCELLED
                    )
                    invalidated = True
                else:
                    member, created = ConversationMember.objects.get_or_create(
                        conversation=conversation,
                        user=responder,
                        defaults={"is_active": True},
                    )
                    if not created and not member.is_active:
                        member.is_active = True
                        member.left_at = None
                        member.role = ConversationMember.Role.MEMBER
                        member.save(update_fields=["is_active", "left_at", "role"])
            if not invalidated:
                result = self.room_invitations.save_status(invitation, status)
            conversation.version += 1
            conversation.save(update_fields=["version"])
        if invalidated:
            raise ConflictError("invitation is no longer valid")
        return result

    def get_group_details(self, conversation_id, user_id):
        conversation = self._get_member_conversation(conversation_id, user_id)
        if conversation.conversation_type != Conversation.ConversationType.GROUP:
            raise NotFoundError("group conversation not found")
        members = list(
            ConversationMember.objects.filter(
                conversation=conversation,
                is_active=True,
            ).select_related("user").order_by("user__username")
        )
        member = next(
            item for item in members if str(item.user_id) == str(user_id)
        )
        role = self._role(conversation, member)
        return conversation, members, role

    def update_group(
        self, conversation_id, user_id, expected_version, *, name=None, description=None
    ):
        with self.db.transaction():
            conversation = self._get_locked_group(conversation_id)
            self._check_version(conversation, expected_version)
            actor = self._get_user(user_id)
            self._require_group_admin(conversation, actor)
            if conversation.is_archived:
                raise ConflictError("conversation is archived")
            fields = []
            if name is not None:
                if not isinstance(name, str) or not name.strip():
                    raise ServiceError("name must be a non-empty string")
                name = name.strip()
                if len(name) > 255:
                    raise ServiceError("name must be 255 characters or fewer")
                conversation.name = name
                fields.append("name")
            if description is not None:
                if not isinstance(description, str):
                    raise ServiceError("description must be a string")
                if len(description) > 4000:
                    raise ServiceError("description must be 4000 characters or fewer")
                conversation.description = description.strip()
                fields.append("description")
            if not fields:
                raise ServiceError("name or description is required")
            conversation.version += 1
            conversation.save(update_fields=[*fields, "version"])
            return conversation

    def cancel_room_invitation(self, invitation_id, user_id, expected_version):
        initial = RoomInvitation.objects.filter(
            invitation_id=invitation_id
        ).only("conversation_id").first()
        if initial is None:
            raise NotFoundError("room invitation not found")
        with self.db.transaction():
            conversation = self._get_locked_group(initial.conversation_id)
            self._check_version(conversation, expected_version)
            invitation = self.room_invitations.get_for_update(invitation_id)
            if invitation is None:
                raise NotFoundError("room invitation not found")
            if invitation.status != RoomInvitation.InvitationStatus.PENDING:
                raise ConflictError("invitation has already been handled")
            actor = self._get_user(user_id)
            if actor != conversation.owner and not (
                invitation.sender_id == actor.user_id
                and self._can_invite(conversation, actor)
            ):
                raise PermissionError("not allowed to cancel this invitation")
            self.room_invitations.save_status(
                invitation, RoomInvitation.InvitationStatus.CANCELLED
            )
            conversation.version += 1
            conversation.save(update_fields=["version"])
            return invitation

    def remove_group_member(
        self, conversation_id, target_id, actor_id, expected_version
    ):
        with self.db.transaction():
            conversation = self._get_locked_group(conversation_id)
            self._check_version(conversation, expected_version)
            actor = self._get_user(actor_id)
            target = self._get_user(target_id)
            self._require_group_admin(conversation, actor)
            if conversation.is_archived:
                raise ConflictError("conversation is archived")
            if str(target_id) == str(actor_id):
                raise ConflictError("use the leave endpoint to remove yourself")
            if target == conversation.owner:
                raise ConflictError("transfer ownership before removing the owner")
            target_member = ConversationMember.objects.select_for_update().filter(
                conversation=conversation, user=target, is_active=True
            ).first()
            if target_member is None:
                raise NotFoundError("active member not found")
            if (
                self._role(conversation, target_member) == "ADMIN"
                and actor != conversation.owner
            ):
                raise PermissionError("only the owner can remove an admin")
            target_member.is_active = False
            target_member.left_at = timezone.now()
            target_member.save(update_fields=["is_active", "left_at"])
            self._cancel_sender_invitations(conversation, target)
            conversation.version += 1
            conversation.save(update_fields=["version"])
            return target_member

    def leave_group(self, conversation_id, user_id, expected_version):
        with self.db.transaction():
            conversation = self._get_locked_group(conversation_id)
            self._check_version(conversation, expected_version)
            user = self._get_user(user_id)
            member = ConversationMember.objects.select_for_update().filter(
                conversation=conversation, user=user, is_active=True
            ).first()
            if member is None:
                raise PermissionError("user is not an active member")
            if user == conversation.owner:
                remaining = ConversationMember.objects.filter(
                    conversation=conversation, is_active=True
                ).exclude(user=user).exists()
                if remaining:
                    raise ConflictError("transfer ownership before leaving")
                conversation.is_archived = True
                conversation.version += 1
                conversation.save(update_fields=["is_archived", "version"])
            member.is_active = False
            member.left_at = timezone.now()
            member.save(update_fields=["is_active", "left_at"])
            self._cancel_sender_invitations(conversation, user)
            if user != conversation.owner:
                conversation.version += 1
                conversation.save(update_fields=["version"])
            return conversation

    def set_member_role(
        self, conversation_id, target_id, actor_id, role, expected_version
    ):
        if role not in (
            ConversationMember.Role.ADMIN,
            ConversationMember.Role.MEMBER,
        ):
            raise ServiceError("role must be ADMIN or MEMBER")
        with self.db.transaction():
            conversation = self._get_locked_group(conversation_id)
            self._check_version(conversation, expected_version)
            actor = self._get_user(actor_id)
            target = self._get_user(target_id)
            if actor != conversation.owner:
                raise PermissionError("only the owner can change member roles")
            if conversation.is_archived:
                raise ConflictError("conversation is archived")
            if target == conversation.owner:
                raise ConflictError("the owner role is managed by ownership transfer")
            member = ConversationMember.objects.select_for_update().filter(
                conversation=conversation, user=target, is_active=True
            ).first()
            if member is None:
                raise NotFoundError("active member not found")
            member.role = role
            member.save(update_fields=["role"])
            conversation.version += 1
            conversation.save(update_fields=["version"])
            return member

    def transfer_ownership(
        self, conversation_id, target_id, actor_id, expected_version
    ):
        with self.db.transaction():
            conversation = self._get_locked_group(conversation_id)
            self._check_version(conversation, expected_version)
            actor = self._get_user(actor_id)
            target = self._get_user(target_id)
            if actor != conversation.owner:
                raise PermissionError("only the owner can transfer ownership")
            if conversation.is_archived:
                raise ConflictError("conversation is archived")
            target_member = ConversationMember.objects.select_for_update().filter(
                conversation=conversation, user=target, is_active=True
            ).first()
            if target_member is None:
                raise NotFoundError("new owner must be an active member")
            old_owner_member = ConversationMember.objects.select_for_update().get(
                conversation=conversation, user=actor, is_active=True
            )
            conversation.owner = target
            conversation.version += 1
            conversation.save(update_fields=["owner", "version"])
            old_owner_member.role = ConversationMember.Role.ADMIN
            old_owner_member.save(update_fields=["role"])
            return conversation

    def archive_group(self, conversation_id, actor_id, expected_version):
        with self.db.transaction():
            conversation = self._get_locked_group(conversation_id)
            self._check_version(conversation, expected_version)
            actor = self._get_user(actor_id)
            if actor != conversation.owner:
                raise PermissionError("only the owner can archive the group")
            if conversation.is_archived:
                return conversation
            conversation.is_archived = True
            conversation.version += 1
            conversation.save(update_fields=["is_archived", "version"])
            return conversation

    def _get_locked_group(self, conversation_id):
        parsed_id = self._parse_id(conversation_id)
        conversation = (
            self.conversations.get_for_update(parsed_id) if parsed_id else None
        )
        if conversation is None:
            raise NotFoundError("group conversation not found")
        if conversation.conversation_type != Conversation.ConversationType.GROUP:
            raise NotFoundError("group conversation not found")
        return conversation

    @staticmethod
    def _check_version(conversation, expected_version):
        if expected_version is None:
            raise PreconditionRequired("If-Match group version is required")
        try:
            version = int(str(expected_version).strip().strip('"'))
        except (TypeError, ValueError) as error:
            raise ServiceError("If-Match must contain a group version") from error
        if version != conversation.version:
            raise PreconditionFailed("group changed; reload before retrying")

    @staticmethod
    def _role(conversation, member):
        if conversation.owner_id == member.user_id:
            return "OWNER"
        return member.role

    @classmethod
    def _can_invite(cls, conversation, user):
        member = ConversationMember.objects.filter(
            conversation=conversation, user=user, is_active=True
        ).first()
        return bool(member and cls._role(conversation, member) in ("OWNER", "ADMIN"))

    @classmethod
    def _require_group_admin(cls, conversation, user):
        if not cls._can_invite(conversation, user):
            raise PermissionError("only the owner or an admin can manage this group")

    @staticmethod
    def _cancel_sender_invitations(conversation, user):
        RoomInvitation.objects.filter(
            conversation=conversation,
            sender=user,
            status=RoomInvitation.InvitationStatus.PENDING,
        ).update(status=RoomInvitation.InvitationStatus.CANCELLED)

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
