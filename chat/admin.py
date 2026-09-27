from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Invitation, User, UserFriend


admin.site.register(User)
admin.site.register(Invitation)
admin.site.register(UserFriend)
