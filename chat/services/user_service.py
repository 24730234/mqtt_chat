import uuid

from django.db import IntegrityError

from ..db_connection import DatabaseConnection
from ..models import Invitation, User
from ..repositories import (
    InvitationRepository,
    UserFriendRepository,
    UserRepository,
)
from .errors import ConflictError, NotFoundError, PermissionError, ServiceError


class UserService:
    PROFILE_FIELDS = {"status", "short_bio", "bio", "sex"}
    MAX_AVATAR_SIZE = 5 * 1024 * 1024
    AVATAR_SIGNATURES = (
        (b"\xFF\xD8\xFF", "jpg"),
        (b"\x89PNG\r\n\x1a\n", "png"),
        (b"GIF87a", "gif"),
        (b"GIF89a", "gif"),
        (b"BM", "bmp"),
    )

    def __init__(self, db=None, users=None, invitations=None, friendships=None):
        self.db = db or DatabaseConnection()
        self.users = users or UserRepository()
        self.invitations = invitations or InvitationRepository()
        self.friendships = friendships or UserFriendRepository()

    @staticmethod
    def _parse_id(value):
        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError, AttributeError):
            return None

    def _get_user(self, value):
        user_id = self._parse_id(value)
        user = self.users.get(user_id) if user_id else None
        if user is None:
            raise NotFoundError("user not found")
        return user

    @classmethod
    def _validated_profile(cls, fields):
        unknown = fields.keys() - cls.PROFILE_FIELDS
        if unknown:
            raise ServiceError(f"unsupported user fields: {', '.join(sorted(unknown))}")

        values = {}
        for field in ("status", "sex", "short_bio", "bio"):
            if field not in fields:
                continue
            value = fields[field]
            if not isinstance(value, str):
                raise ServiceError(f"{field} must be a string")
            if field == "status" and value not in User.PresenceStatus.values:
                raise ServiceError("status must be online or offline")
            if field == "sex" and value not in ("", *User.Sex.values):
                raise ServiceError("sex must be female or male")
            if field == "short_bio" and len(value) > 160:
                raise ServiceError("short_bio must be 160 characters or fewer")
            values[field] = value
        return values

    def create_user(self, username, **fields):
        username = username.strip() if isinstance(username, str) else ""
        if not username:
            raise ServiceError("username is required")
        profile = self._validated_profile(fields)
        try:
            return self.users.create(username, **profile)
        except IntegrityError as exc:
            raise ConflictError("username already exists") from exc

    def update_user(self, user_id, **fields):
        user = self._get_user(user_id)
        username = fields.pop("username", None)
        if username is not None:
            username = username.strip() if isinstance(username, str) else ""
            if not username:
                raise ServiceError("username is required")
        profile = self._validated_profile(fields)
        if username is None and not profile:
            raise ServiceError("at least one user field is required")
        if username is not None:
            profile["username"] = username
        try:
            return self.users.update_profile(user, **profile)
        except IntegrityError as exc:
            raise ConflictError("username already exists") from exc

    @classmethod
    def _avatar_extension(cls, avatar):
        if avatar.size > cls.MAX_AVATAR_SIZE:
            raise ServiceError("avatar must be 5 MB or smaller")

        signature = avatar.read(12)
        avatar.seek(0)
        for prefix, extension in cls.AVATAR_SIGNATURES:
            if signature.startswith(prefix):
                return extension
        if signature.startswith(b"RIFF") and signature[8:12] == b"WEBP":
            return "webp"
        raise ServiceError("avatar must be a JPEG, PNG, GIF, BMP, or WebP image")

    def update_avatar(self, user_id, avatar):
        user = self._get_user(user_id)
        if avatar is None:
            raise ServiceError("avatar file is required")
        extension = self._avatar_extension(avatar)
        avatar.name = f"avatar.{extension}"

        old_name = user.avatar.name if user.avatar else None
        self.users.update_avatar(user, avatar)
        if old_name and old_name != user.avatar.name:
            user.avatar.storage.delete(old_name)
        return user

    def remove_avatar(self, user_id):
        user = self._get_user(user_id)
        if not user.avatar:
            return user
        old_name = user.avatar.name
        self.users.remove_avatar(user)
        user.avatar.storage.delete(old_name)
        return user

    def search_users(self, username):
        return self.users.search(username.strip())

    def send_invitation(self, sender_id, recipient_id):
        sender = self._get_user(sender_id)
        recipient = self._get_user(recipient_id)
        if sender == recipient:
            raise ServiceError("cannot invite yourself")
        if self.users.are_friends(sender, recipient):
            raise ConflictError("users are already friends")
        if self.invitations.has_pending_between(sender, recipient):
            raise ConflictError("a pending invitation already exists")
        return self.invitations.create(sender, recipient)

    def respond_to_invitation(self, invitation_id, responder_id, status):
        invitation = self.invitations.get(self._parse_id(invitation_id))
        if invitation is None:
            raise NotFoundError("invitation not found")
        responder = self._get_user(responder_id)
        if responder != invitation.user:
            raise PermissionError("only the recipient can respond")
        if status not in (
            Invitation.InvitationStatus.ACCEPT,
            Invitation.InvitationStatus.REJECT,
        ):
            raise ServiceError("status must be ACCEPT or REJECT")
        if invitation.status != Invitation.InvitationStatus.PENDING:
            raise ConflictError("invitation has already been handled")
        with self.db.transaction():
            self.invitations.save_status(invitation, status)
            if status == Invitation.InvitationStatus.ACCEPT:
                try:
                    self.friendships.create_pair(invitation.sender, invitation.user)
                except IntegrityError as exc:
                    raise ConflictError("friendship already exists") from exc
        return invitation

    def list_friends(self, user_id):
        return self.users.friends(self._get_user(user_id))

    def delete_friend(self, user_id, friend_id):
        user = self._get_user(user_id)
        friend = self._get_user(friend_id)
        if not self.users.are_friends(user, friend):
            raise NotFoundError("friendship not found")
        self.users.remove_friendship(user, friend)

