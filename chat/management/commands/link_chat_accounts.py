import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from chat.models import User


class Command(BaseCommand):
    help = "Link existing chat profiles to explicitly mapped Django accounts."

    def add_arguments(self, parser):
        parser.add_argument("mapping_file")

    def handle(self, *args, **options):
        try:
            mappings = json.loads(
                Path(options["mapping_file"]).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f"Could not read account mapping: {error}") from error
        if not isinstance(mappings, list):
            raise CommandError("Mapping file must contain a JSON array.")

        auth_model = get_user_model()
        try:
            with transaction.atomic():
                for item in mappings:
                    if not isinstance(item, dict):
                        raise CommandError("Each mapping must be a JSON object.")
                    profile = User.objects.select_for_update().filter(
                        user_id=item.get("chat_user_id")
                    ).first()
                    auth_user = auth_model.objects.select_for_update().filter(
                        username=item.get("auth_username")
                    ).first()
                    if profile is None or auth_user is None:
                        raise CommandError("A mapped chat profile or auth account does not exist.")
                    if not auth_user.is_active:
                        raise CommandError(f"Account {auth_user.username} is inactive.")
                    if profile.auth_user_id not in (None, auth_user.pk):
                        raise CommandError(f"Profile {profile.user_id} is already linked.")
                    if User.objects.filter(auth_user=auth_user).exclude(
                        user_id=profile.user_id
                    ).exists():
                        raise CommandError(
                            f"Account {auth_user.username} is already linked to another profile."
                        )
                    if profile.username != auth_user.get_username():
                        raise CommandError(
                            f"Account and profile usernames differ for {profile.user_id}; "
                            "reconcile the names explicitly before linking."
                        )
                    profile.auth_user = auth_user
                    profile.save(update_fields=["auth_user"])
        except AttributeError as error:
            raise CommandError("A mapped account is linked to a different profile.") from error
        self.stdout.write(self.style.SUCCESS(f"Linked {len(mappings)} chat profile(s)."))
