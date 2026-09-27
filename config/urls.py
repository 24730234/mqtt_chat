"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from chat import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/users/", views.create_user, name="create-user"),
    path("api/users/search/", views.search_users, name="search-users"),
    path("api/users/<uuid:user_id>/", views.update_user, name="update-user"),
    path(
        "api/users/<uuid:user_id>/avatar/",
        views.update_user_avatar,
        name="update-user-avatar",
    ),
    path("api/users/<uuid:user_id>/friends/", views.list_friends, name="list-friends"),
    path(
        "api/users/<uuid:user_id>/friends/<uuid:friend_id>/",
        views.delete_friend,
        name="delete-friend",
    ),
    path("api/invitations/", views.send_invitation, name="send-invitation"),
    path(
        "api/invitations/<uuid:invitation_id>/respond/",
        views.respond_to_invitation,
        name="respond-to-invitation",
    ),
    path("api/conversations/", views.create_conversation, name="create-conversation"),
    path(
        "api/conversations/<uuid:conversation_id>/messages/",
        views.load_message_history,
        name="load-message-history",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
