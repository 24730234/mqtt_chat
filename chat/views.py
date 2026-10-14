import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .authentication import require_actor_match, require_chat_user
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
    members = conversation.members.filter(is_active=True).select_related("user").order_by("user__username")
    return {
        "conversation_id": str(conversation.conversation_id),
        "name": conversation.name,
        "type": conversation.conversation_type,
        "description": conversation.description,
        "owner_id": str(conversation.owner_id) if conversation.owner_id else None,
        "is_archived": conversation.is_archived,
        "version": conversation.version,
        "created_at": conversation.created_at.isoformat(),
        "members": [
            {
                **_user_data(member.user),
                "role": (
                    "OWNER"
                    if member.user_id == conversation.owner_id
                    else member.role
                ),
            }
            for member in members
        ],
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


@require_http_methods(["POST"])
def create_user(request):
    return JsonResponse(
        {"error": "use /api/auth/register/ to create an account"},
        status=410,
    )


@require_chat_user
@require_http_methods(["PUT", "PATCH"])
def update_user(request, user_id):
    data = _body(request) or {}
    mismatch = require_actor_match(request, user_id)
    if mismatch:
        return mismatch
    try:
        return JsonResponse(
            _user_data(ChatService().update_user(request.chat_user.user_id, **data))
        )
    except ServiceError as error:
        return _service_error(error)


@require_chat_user
@require_http_methods(["POST", "DELETE"])
def update_user_avatar(request, user_id):
    mismatch = require_actor_match(request, user_id)
    if mismatch:
        return mismatch
    service = ChatService()
    try:
        if request.method == "DELETE":
            user = service.remove_avatar(request.chat_user.user_id)
        else:
            user = service.update_avatar(request.chat_user.user_id, request.FILES.get("avatar"))
        return JsonResponse(_user_data(user))
    except ServiceError as error:
        return _service_error(error)


@require_chat_user
@require_http_methods(["GET"])
def search_users(request):
    users = ChatService().search_users(request.GET.get("username", ""))
    return JsonResponse({"users": [_user_data(user) for user in users]})


@require_chat_user
@require_http_methods(["POST"])
def send_invitation(request):
    data = _body(request) or {}
    mismatch = require_actor_match(request, data.get("sender_id"))
    if mismatch:
        return mismatch
    try:
        invitation = ChatService().send_invitation(
            request.chat_user.user_id, data.get("user_id")
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


@require_chat_user
@require_http_methods(["POST"])
def respond_to_invitation(request, invitation_id):
    data = _body(request) or {}
    mismatch = require_actor_match(request, data.get("user_id"))
    if mismatch:
        return mismatch
    try:
        invitation = ChatService().respond_to_invitation(
            invitation_id, request.chat_user.user_id, data.get("status")
        )
        return JsonResponse(
            {"invitation_id": str(invitation.invitation_id), "status": invitation.status}
        )
    except ServiceError as error:
        return _service_error(error)


@require_chat_user
@require_http_methods(["GET"])
def list_friends(request, user_id):
    mismatch = require_actor_match(request, user_id)
    if mismatch:
        return mismatch
    try:
        online_only = request.GET.get("online", "").lower()
        if online_only not in ("", "true", "false"):
            raise ServiceError("online must be true or false")
        result = ChatService().list_friends_page(
            request.chat_user.user_id,
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


@require_chat_user
@require_http_methods(["GET"])
def list_invitations(request, user_id):
    mismatch = require_actor_match(request, user_id)
    if mismatch:
        return mismatch
    try:
        invitations = ChatService().list_invitations(request.chat_user.user_id)
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
                                    "version": invitation.conversation.version,
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


@require_chat_user
@require_http_methods(["POST"])
def send_room_invitation(request):
    data = _body(request) or {}
    mismatch = require_actor_match(request, data.get("sender_id"))
    if mismatch:
        return mismatch
    try:
        version = request.headers.get("If-Match")
        invitation = ChatService().send_room_invitation(
            request.chat_user.user_id,
            data.get("user_id"),
            data.get("conversation_id"),
            version,
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


@require_chat_user
@require_http_methods(["POST"])
def respond_to_room_invitation(request, invitation_id):
    data = _body(request) or {}
    mismatch = require_actor_match(request, data.get("user_id"))
    if mismatch:
        return mismatch
    try:
        invitation = ChatService().respond_to_room_invitation(
            invitation_id,
            request.chat_user.user_id,
            data.get("status"),
            request.headers.get("If-Match"),
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


@require_chat_user
@require_http_methods(["DELETE"])
def delete_friend(request, user_id, friend_id):
    mismatch = require_actor_match(request, user_id)
    if mismatch:
        return mismatch
    try:
        ChatService().delete_friend(request.chat_user.user_id, friend_id)
        return JsonResponse({"deleted": True})
    except ServiceError as error:
        return _service_error(error)


@require_chat_user
@require_http_methods(["POST"])
def create_conversation(request):
    data = _body(request) or {}
    mismatch = require_actor_match(request, data.get("user_id"))
    if mismatch:
        return mismatch
    try:
        conversation = ChatService().create_conversation(
            creator_id=request.chat_user.user_id,
            conversation_type=data.get("type"),
            username=data.get("username"),
            usernames=data.get("usernames"),
            name=data.get("name"),
        )
        return JsonResponse(_conversation_data(conversation), status=201)
    except ServiceError as error:
        return _service_error(error)


@require_chat_user
@require_http_methods(["GET"])
def list_conversations(request, user_id):
    mismatch = require_actor_match(request, user_id)
    if mismatch:
        return mismatch
    try:
        conversations = ChatService().list_conversations(request.chat_user.user_id)
        return JsonResponse(
            {
                "conversations": [
                    {
                        "conversation_id": str(conversation.conversation_id),
                        "name": conversation.name,
                        "type": conversation.conversation_type,
                        "description": conversation.description,
                        "owner_id": str(conversation.owner_id) if conversation.owner_id else None,
                        "is_archived": conversation.is_archived,
                        "version": conversation.version,
                        "created_at": conversation.created_at.isoformat(),
                        "unread_count": conversation.unread_count,
                        "members": [
                            {
                                **_user_data(member.user),
                                "role": (
                                    "OWNER"
                                    if member.user_id == conversation.owner_id
                                    else member.role
                                ),
                            }
                            for member in conversation.members.filter(
                                is_active=True
                            ).select_related("user")
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


@require_chat_user
@require_http_methods(["GET"])
def search_messages(request, conversation_id):
    mismatch = require_actor_match(request, request.GET.get("user_id"))
    if mismatch:
        return mismatch
    try:
        conversation, messages = ChatService().search_messages(
            conversation_id=conversation_id,
            user_id=request.chat_user.user_id,
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


@require_chat_user
@require_http_methods(["GET"])
def load_message_history(request, conversation_id):
    mismatch = require_actor_match(request, request.GET.get("user_id"))
    if mismatch:
        return mismatch
    try:
        conversation, messages = ChatService().load_history(
            conversation_id=conversation_id,
            user_id=request.chat_user.user_id,
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


@require_chat_user
@require_http_methods(["GET", "PATCH"])
def conversation_detail(request, conversation_id):
    service = ChatService()
    try:
        if request.method == "PATCH":
            data = _body(request)
            if data is None:
                return JsonResponse(
                    {"error": "request body must be a JSON object"}, status=400
                )
            conversation = service.update_group(
                conversation_id,
                request.chat_user.user_id,
                request.headers.get("If-Match"),
                name=data.get("name"),
                description=data.get("description"),
            )
        conversation, members, role = service.get_group_details(
            conversation_id, request.chat_user.user_id
        )
        is_admin = role in ("OWNER", "ADMIN") and not conversation.is_archived
        result = _conversation_data(conversation)
        result["members"] = [
            {
                **_user_data(member.user),
                "role": "OWNER" if member.user_id == conversation.owner_id else member.role,
                "is_active": member.is_active,
            }
            for member in members
        ]
        result["pending_invitations"] = [
            _user_data(invitation.user)
            for invitation in conversation.room_invitations.filter(
                status="PENDING"
            ).select_related("user")
        ]
        result["role"] = role
        result["permissions"] = {
            "can_edit": is_admin,
            "can_invite": is_admin,
            "can_remove_members": is_admin,
            "can_manage_roles": role == "OWNER" and not conversation.is_archived,
            "can_transfer_ownership": role == "OWNER" and not conversation.is_archived,
            "can_archive": role == "OWNER" and not conversation.is_archived,
            "can_leave": True,
        }
        return JsonResponse(result)
    except ServiceError as error:
        return _service_error(error)


@require_chat_user
@require_http_methods(["DELETE"])
def cancel_room_invitation(request, invitation_id):
    try:
        ChatService().cancel_room_invitation(
            invitation_id,
            request.chat_user.user_id,
            request.headers.get("If-Match"),
        )
        return JsonResponse({"cancelled": True})
    except ServiceError as error:
        return _service_error(error)


@require_chat_user
@require_http_methods(["DELETE"])
def remove_group_member(request, conversation_id, user_id):
    try:
        ChatService().remove_group_member(
            conversation_id,
            user_id,
            request.chat_user.user_id,
            request.headers.get("If-Match"),
        )
        return JsonResponse({"removed": True})
    except ServiceError as error:
        return _service_error(error)


@require_chat_user
@require_http_methods(["POST"])
def leave_group(request, conversation_id):
    try:
        ChatService().leave_group(
            conversation_id,
            request.chat_user.user_id,
            request.headers.get("If-Match"),
        )
        return JsonResponse({"left": True})
    except ServiceError as error:
        return _service_error(error)


@require_chat_user
@require_http_methods(["PATCH"])
def change_group_member_role(request, conversation_id, user_id):
    data = _body(request)
    if data is None:
        return JsonResponse(
            {"error": "request body must be a JSON object"}, status=400
        )
    try:
        member = ChatService().set_member_role(
            conversation_id,
            user_id,
            request.chat_user.user_id,
            data.get("role"),
            request.headers.get("If-Match"),
        )
        return JsonResponse({"user_id": str(member.user_id), "role": member.role})
    except ServiceError as error:
        return _service_error(error)


@require_chat_user
@require_http_methods(["POST"])
def transfer_group_ownership(request, conversation_id):
    data = _body(request)
    if data is None:
        return JsonResponse(
            {"error": "request body must be a JSON object"}, status=400
        )
    try:
        conversation = ChatService().transfer_ownership(
            conversation_id,
            data.get("new_owner_id"),
            request.chat_user.user_id,
            request.headers.get("If-Match"),
        )
        return JsonResponse(
            {
                "owner_id": str(conversation.owner_id),
                "version": conversation.version,
            }
        )
    except ServiceError as error:
        return _service_error(error)


@require_chat_user
@require_http_methods(["POST"])
def archive_group(request, conversation_id):
    try:
        conversation = ChatService().archive_group(
            conversation_id,
            request.chat_user.user_id,
            request.headers.get("If-Match"),
        )
        return JsonResponse(
            {"is_archived": conversation.is_archived, "version": conversation.version}
        )
    except ServiceError as error:
        return _service_error(error)
