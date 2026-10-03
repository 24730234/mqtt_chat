from .conversation_service import ConversationService
from .message_service import MessageService
from .user_service import UserService


class ChatService:
    """Application-level facade for the chat app's user and conversation services."""

    def __init__(self, users=None, conversations=None, messages=None):
        self.user_service = users or UserService()
        self.conversation_service = conversations or ConversationService()
        self.message_service = messages or MessageService()

    def create_user(self, username, **fields):
        return self.user_service.create_user(username, **fields)

    def update_user(self, user_id, **fields):
        return self.user_service.update_user(user_id, **fields)

    def update_avatar(self, user_id, avatar):
        return self.user_service.update_avatar(user_id, avatar)

    def remove_avatar(self, user_id):
        return self.user_service.remove_avatar(user_id)

    def search_users(self, username):
        return self.user_service.search_users(username)

    def send_invitation(self, sender_id, recipient_id):
        return self.user_service.send_invitation(sender_id, recipient_id)

    def respond_to_invitation(self, invitation_id, responder_id, status):
        return self.user_service.respond_to_invitation(
            invitation_id, responder_id, status
        )

    def list_friends(self, user_id):
        return self.user_service.list_friends(user_id)

    def delete_friend(self, user_id, friend_id):
        return self.user_service.delete_friend(user_id, friend_id)

    def create_conversation(
        self,
        creator_id,
        conversation_type,
        username=None,
        usernames=None,
        name=None,
    ):
        return self.conversation_service.create_conversation(
            creator_id=creator_id,
            conversation_type=conversation_type,
            username=username,
            usernames=usernames,
            name=name,
        )

    def load_history(self, conversation_id, user_id, before_seq=None, limit=50):
        return self.conversation_service.load_history(
            conversation_id=conversation_id,
            user_id=user_id,
            before_seq=before_seq,
            limit=limit,
        )

    def search_messages(
        self, conversation_id, user_id, query, before_seq=None, limit=50
    ):
        return self.conversation_service.search_messages(
            conversation_id=conversation_id,
            user_id=user_id,
            query=query,
            before_seq=before_seq,
            limit=limit,
        )

    def send_message(
        self,
        sender_id,
        conversation_id,
        client_message_id,
        content,
        reply_to_message_id=None,
    ):
        return self.message_service.send_message(
            sender_id=sender_id,
            conversation_id=conversation_id,
            client_message_id=client_message_id,
            content=content,
            reply_to_message_id=reply_to_message_id,
        )
