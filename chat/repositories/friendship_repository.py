from ..models import UserFriend


class UserFriendRepository:
    def create_pair(self, first, second):
        UserFriend.objects.bulk_create(
            [
                UserFriend(user=first, friend=second),
                UserFriend(user=second, friend=first),
            ]
        )
