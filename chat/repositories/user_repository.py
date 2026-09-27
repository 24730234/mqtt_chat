from django.db.models import Q

from ..models import User, UserFriend


class UserRepository:
    def create(self, username, **fields):
        return User.objects.create(username=username, **fields)

    def get(self, user_id):
        return User.objects.filter(user_id=user_id).first()

    def get_by_username(self, username):
        return User.objects.filter(username=username).first()

    def update_username(self, user, username):
        user.username = username
        user.save(update_fields=["username"])
        return user

    def update_profile(self, user, **fields):
        for field, value in fields.items():
            setattr(user, field, value)
        user.save(update_fields=list(fields))
        return user

    def update_status(self, user_id, status):
        return User.objects.filter(user_id=user_id).update(status=status)

    def update_avatar(self, user, avatar):
        user.avatar = avatar
        user.save(update_fields=["avatar"])
        return user

    def remove_avatar(self, user):
        user.avatar = None
        user.save(update_fields=["avatar"])
        return user

    def search(self, username):
        return User.objects.filter(username__icontains=username).order_by("username")

    def are_friends(self, first, second):
        return UserFriend.objects.filter(user=first, friend=second).exists()

    def friends(self, user):
        return User.objects.filter(friend_of__user=user).distinct().order_by("username")

    def remove_friendship(self, first, second):
        return UserFriend.objects.filter(
            Q(user=first, friend=second) | Q(user=second, friend=first)
        ).delete()[0]
