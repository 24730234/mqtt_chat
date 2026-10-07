from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Invitation, RoomInvitation, User, UserFriend


admin.site.register(User)
admin.site.register(Invitation)
admin.site.register(RoomInvitation)
admin.site.register(UserFriend)
