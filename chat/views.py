import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Invitation
from .services import ChatService, ServiceError


def _body(request):
    try:
        value = json.loads(request.body or b"{}")
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _user_data(user):
    return {
        "user_id": str(user.user_id),
        "username": user.username,
        "avatar_url": user.avatar.url if user.avatar else None,
        "status": user.status,
        "short_bio": user.short_bio,
        "bio": user.bio,
        "sex": user.sex or None,
        "created_at": user.created_at.isoformat(),
    }


def _conversation_data(conversation):
    members = conversation.members.select_related("user").order_by("user__username")
    return {
        "conversation_id": str(conversation.conversation_id),
        "name": conversation.name,
        "type": conversation.conversation_type,
        "created_at": conversation.created_at.isoformat(),
        "members": [_user_data(member.user) for member in members],
    }


def _message_data(message):
    return {
        "message_id": str(message.message_id),
        "sender": _user_data(message.sender),
        "content": message.content,
        "seq": message.seq,
        "created_at": message.created_at.isoformat(),
        "reply_to": (
            {
                "message_id": str(message.reply_to.message_id),
                "content": message.reply_to.content,
            }
            if message.reply_to_id
            else None
        ),
        "read_by": [
            _user_data(receipt.user)
            for receipt in message.receipts.all()
            if receipt.status == "READ"
        ],
    }


def _service_error(error):
    return JsonResponse({"error": str(error)}, status=error.status_code)


@csrf_exempt
@require_http_methods(["POST"])
def create_user(request):
    data = _body(request) or {}
    try:
        profile = {
            field: data[field]
            for field in ("status", "short_bio", "bio", "sex")
            if field in data
        }
        user = ChatService().create_user(data.get("username"), **profile)
        return JsonResponse(_user_data(user), status=201)
    except ServiceError as error:
        return _service_error(error)


@csrf_exempt
@require_http_methods(["PUT", "PATCH"])
def update_user(request, user_id):
    data = _body(request) or {}
    try:
        return JsonResponse(_user_data(ChatService().update_user(user_id, **data)))
    except ServiceError as error:
        return _service_error(error)


@csrf_exempt
@require_http_methods(["POST", "DELETE"])
def update_user_avatar(request, user_id):
    service = ChatService()
    try:
        if request.method == "DELETE":
            user = service.remove_avatar(user_id)
        else:
            user = service.update_avatar(user_id, request.FILES.get("avatar"))
        return JsonResponse(_user_data(user))
    except ServiceError as error:
        return _service_error(error)


@require_http_methods(["GET"])
def search_users(request):
    users = ChatService().search_users(request.GET.get("username", ""))
    return JsonResponse({"users": [_user_data(user) for user in users]})


@csrf_exempt
@require_http_methods(["POST"])
def send_invitation(request):
    data = _body(request) or {}
    try:
        invitation = ChatService().send_invitation(
            data.get("sender_id"), data.get("user_id")
        )
        return JsonResponse(
            {
                "invitation_id": str(invitation.invitation_id),
                "sender_id": str(invitation.sender_id),
                "user_id": str(invitation.user_id),
                "status": invitation.status,
                "send_time": invitation.send_time.isoformat(),
            },
            status=201,
        )
    except ServiceError as error:
        return _service_error(error)


@csrf_exempt
@require_http_methods(["POST"])
def respond_to_invitation(request, invitation_id):
    data = _body(request) or {}
    try:
        invitation = ChatService().respond_to_invitation(
            invitation_id, data.get("user_id"), data.get("status")
        )
        return JsonResponse(
            {"invitation_id": str(invitation.invitation_id), "status": invitation.status}
        )
    except ServiceError as error:
        return _service_error(error)


@require_http_methods(["GET"])
def list_friends(request, user_id):
    try:
        online_only = request.GET.get("online", "").lower()
        if online_only not in ("", "true", "false"):
            raise ServiceError("online must be true or false")
        result = ChatService().list_friends_page(
            user_id,
            query=request.GET.get("q", ""),
            online_only=online_only == "true",
            cursor=request.GET.get("cursor"),
            limit=request.GET.get("limit", 25),
        )
        return JsonResponse(
            {
                "friends": [_user_data(friend) for friend in result["friends"]],
                "total": result["total"],
                "online_total": result["online_total"],
                "next_cursor": result["next_cursor"],
            }
        )
    except ServiceError as error:
        return _service_error(error)


@require_http_methods(["GET"])
def list_invitations(request, user_id):
    try:
        invitations = ChatService().list_invitations(user_id)
        return JsonResponse(
            {
                key: [
                    {
                        "invitation_id": str(invitation.invitation_id),
                        "sender": _user_data(invitation.sender),
                        "recipient": _user_data(invitation.user),
                        **(
                            {
                                "conversation": {
                                    "conversation_id": str(
                                        invitation.conversation.conversation_id
                                    ),
                                    "name": invitation.conversation.name,
                                    "type": invitation.conversation.conversation_type,
                                }
                            }
                            if key.startswith("room_")
                            else {}
                        ),
                        "status": invitation.status,
                        "send_time": invitation.send_time.isoformat(),
                    }
                    for invitation in items
                ]
                for key, items in invitations.items()
            }
        )
    except ServiceError as error:
        return _service_error(error)


@csrf_exempt
@require_http_methods(["POST"])
def send_room_invitation(request):
    data = _body(request) or {}
    try:
        invitation = ChatService().send_room_invitation(
            data.get("sender_id"),
            data.get("user_id"),
            data.get("conversation_id"),
        )
        return JsonResponse(
            {
                "invitation_id": str(invitation.invitation_id),
                "conversation_id": str(invitation.conversation_id),
                "sender_id": str(invitation.sender_id),
                "user_id": str(invitation.user_id),
                "status": invitation.status,
                "send_time": invitation.send_time.isoformat(),
            },
            status=201,
        )
    except ServiceError as error:
        return _service_error(error)


@csrf_exempt
@require_http_methods(["POST"])
def respond_to_room_invitation(request, invitation_id):
    data = _body(request) or {}
    try:
        invitation = ChatService().respond_to_room_invitation(
            invitation_id, data.get("user_id"), data.get("status")
        )
        return JsonResponse(
            {
                "invitation_id": str(invitation.invitation_id),
                "conversation_id": str(invitation.conversation_id),
                "status": invitation.status,
            }
        )
    except ServiceError as error:
        return _service_error(error)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_friend(request, user_id, friend_id):
    try:
        ChatService().delete_friend(user_id, friend_id)
        return JsonResponse({"deleted": True})
    except ServiceError as error:
        return _service_error(error)


@csrf_exempt
@require_http_methods(["POST"])
def create_conversation(request):
    data = _body(request) or {}
    try:
        conversation = ChatService().create_conversation(
            creator_id=data.get("user_id"),
            conversation_type=data.get("type"),
            username=data.get("username"),
            usernames=data.get("usernames"),
            name=data.get("name"),
        )
        return JsonResponse(_conversation_data(conversation), status=201)
    except ServiceError as error:
        return _service_error(error)


@require_http_methods(["GET"])
def list_conversations(request, user_id):
    try:
        conversations = ChatService().list_conversations(user_id)
        return JsonResponse(
            {
                "conversations": [
                    {
                        "conversation_id": str(conversation.conversation_id),
                        "name": conversation.name,
                        "type": conversation.conversation_type,
                        "created_at": conversation.created_at.isoformat(),
                        "unread_count": conversation.unread_count,
                        "members": [
                            _user_data(member.user)
                            for member in conversation.members.all()
                        ],
                        "last_message": (
                            {
                                "message_id": str(conversation.last_message.message_id),
                                "content": conversation.last_message.content,
                                "seq": conversation.last_message.seq,
                                "created_at": conversation.last_message.created_at.isoformat(),
                                "sender": _user_data(conversation.last_message.sender),
                                "read_by": [
                                    _user_data(receipt.user)
                                    for receipt in conversation.last_message.receipts.all()
                                    if receipt.status == "READ"
                                ],
                            }
                            if conversation.last_message
                            else None
                        ),
                    }
                    for conversation in conversations
                ]
            }
        )
    except ServiceError as error:
        return _service_error(error)


@require_http_methods(["GET"])
def search_messages(request, conversation_id):
    try:
        conversation, messages = ChatService().search_messages(
            conversation_id=conversation_id,
            user_id=request.GET.get("user_id"),
            query=request.GET.get("q"),
            before_seq=request.GET.get("before_seq"),
            limit=request.GET.get("limit", 50),
        )
        return JsonResponse(
            {
                "conversation_id": str(conversation.conversation_id),
                "query": request.GET.get("q", "").strip(),
                "messages": [_message_data(message) for message in messages],
            }
        )
    except ServiceError as error:
        return _service_error(error)


@require_http_methods(["GET"])
def load_message_history(request, conversation_id):
    try:
        conversation, messages = ChatService().load_history(
            conversation_id=conversation_id,
            user_id=request.GET.get("user_id"),
            before_seq=request.GET.get("before_seq"),
            limit=request.GET.get("limit", 50),
        )
        return JsonResponse(
            {
                "conversation_id": str(conversation.conversation_id),
                "messages": [_message_data(message) for message in messages],
            }
        )
    except ServiceError as error:
        return _service_error(error)
