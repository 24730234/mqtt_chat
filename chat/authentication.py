from datetime import datetime, timezone
from functools import wraps
import math

from django.contrib.auth import logout
from django.http import JsonResponse

from .models import User


def chat_user_for_request(request):
    auth_user = getattr(request, "user", None)
    if auth_user is None or not auth_user.is_authenticated or not auth_user.is_active:
        return None

    expires_at = request.session.get("chat_auth_expires_at")
    try:
        expires_at = float(expires_at)
        if not math.isfinite(expires_at) or datetime.now(timezone.utc).timestamp() >= expires_at:
            logout(request)
            return None
    except (TypeError, ValueError):
        logout(request)
        return None

    try:
        return auth_user.chat_profile
    except User.DoesNotExist:
        return None


def require_chat_user(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        user = chat_user_for_request(request)
        if user is None:
            response = JsonResponse({"error": "authentication required"}, status=401)
            response["Cache-Control"] = "no-store"
            return response
        request.chat_user = user
        return view(request, *args, **kwargs)

    return wrapped


def require_actor_match(request, actor_id):
    if actor_id is not None and str(actor_id) != str(request.chat_user.user_id):
        return JsonResponse({"error": "actor does not match authenticated user"}, status=403)
    return None
