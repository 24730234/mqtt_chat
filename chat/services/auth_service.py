from datetime import timedelta

from django.contrib.auth import authenticate, get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import User
from ..username_validation import validate_auth_username
from .errors import AuthenticationError, ConflictError, ServiceError


class AuthService:
    SESSION_SECONDS = 8 * 60 * 60
    REMEMBER_SECONDS = 7 * 24 * 60 * 60

    @staticmethod
    def _validated_username(value):
        username = value.strip() if isinstance(value, str) else ""
        if not username:
            raise ServiceError("username is required")
        if len(username) > 100:
            raise ServiceError("username must be 100 characters or fewer")
        try:
            validate_auth_username(username)
        except ValidationError as error:
            raise ServiceError(" ".join(error.messages)) from error
        return username

    def register(self, username, password, password_confirm):
        username = self._validated_username(username)
        if not isinstance(password, str) or not password:
            raise ServiceError("password is required")
        if password != password_confirm:
            raise ServiceError("password confirmation does not match")

        auth_model = get_user_model()
        candidate = auth_model(username=username)
        try:
            password_validation.validate_password(password, candidate)
        except ValidationError as error:
            raise ServiceError(" ".join(error.messages)) from error

        try:
            with transaction.atomic():
                auth_user = auth_model.objects.create_user(
                    username=username,
                    password=password,
                )
                profile = User.objects.create(
                    username=username,
                    auth_user=auth_user,
                )
        except IntegrityError as error:
            raise ConflictError("username already exists") from error
        return profile

    def authenticate(self, request, username, password):
        username = self._validated_username(username)
        if not isinstance(password, str) or not password:
            raise ServiceError("password is required")
        auth_user = authenticate(request, username=username, password=password)
        if auth_user is None or not auth_user.is_active:
            raise AuthenticationError("invalid username or password")
        try:
            profile = auth_user.chat_profile
        except User.DoesNotExist as error:
            raise AuthenticationError(
                "account is not linked to a chat profile"
            ) from error
        return profile

    @classmethod
    def session_expiry(cls, remember_me):
        return cls.REMEMBER_SECONDS if remember_me is True else cls.SESSION_SECONDS

    @staticmethod
    def expires_at(seconds):
        return timezone.now() + timedelta(seconds=seconds)
