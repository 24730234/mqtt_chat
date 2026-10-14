from django.contrib.auth import get_user_model


def validate_auth_username(username):
    auth_model = get_user_model()
    username_field = auth_model._meta.get_field(auth_model.USERNAME_FIELD)
    username_field.run_validators(username)
