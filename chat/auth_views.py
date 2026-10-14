import json
from datetime import datetime, timezone

from django.contrib.auth import login, logout
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .authentication import chat_user_for_request
from .services import AuthService, ServiceError
from .views import _user_data


def _body(request):
    try:
        data = json.loads(request.body or b"{}")
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _error(error):
    return JsonResponse({"error": str(error)}, status=error.status_code)


@ensure_csrf_cookie
@require_http_methods(["GET"])
def csrf_token(request):
    response = JsonResponse({"csrfToken": get_token(request)})
    response["Cache-Control"] = "no-store"
    return response


def csrf_failure(request, reason=""):
    response = JsonResponse({"error": "CSRF verification failed"}, status=403)
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["POST"])
def register(request):
    data = _body(request)
    if data is None:
        return JsonResponse({"error": "request body must be a JSON object"}, status=400)
    try:
        user = AuthService().register(
            data.get("username"),
            data.get("password"),
            data.get("password_confirm"),
        )
    except ServiceError as error:
        return _error(error)
    response = JsonResponse({"user": _user_data(user)}, status=201)
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["POST"])
def login_view(request):
    data = _body(request)
    if data is None:
        return JsonResponse({"error": "request body must be a JSON object"}, status=400)
    remember_me = data.get("remember_me", False)
    if not isinstance(remember_me, bool):
        return JsonResponse({"error": "remember_me must be a boolean"}, status=400)
    service = AuthService()
    try:
        user = service.authenticate(request, data.get("username"), data.get("password"))
    except ServiceError as error:
        return _error(error)

    seconds = service.session_expiry(remember_me)
    login(request, user.auth_user)
    expires_at = service.expires_at(seconds)
    request.session["chat_auth_expires_at"] = expires_at.timestamp()
    request.session.set_expiry(seconds if remember_me else 0)
    response = JsonResponse(
        {
            "user": _user_data(user),
            "expires_at": expires_at.isoformat(),
            "csrfToken": get_token(request),
        }
    )
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["GET"])
def me(request):
    user = chat_user_for_request(request)
    if user is None:
        response = JsonResponse({"error": "authentication required"}, status=401)
    else:
        response = JsonResponse(
            {
                "user": _user_data(user),
                "expires_at": datetime.fromtimestamp(
                    float(request.session["chat_auth_expires_at"]),
                    tz=timezone.utc,
                ).isoformat(),
            }
        )
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["POST"])
def logout_view(request):
    logout(request)
    response = HttpResponse(status=204)
    response["Cache-Control"] = "no-store"
    return response
