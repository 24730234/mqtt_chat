import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from chat.models import Conversation, ConversationMember


class Command(BaseCommand):
    help = "Assign owners to existing groups from a reviewed UUID mapping."

    def add_arguments(self, parser):
        parser.add_argument("mapping_file")

    def handle(self, *args, **options):
        try:
            mappings = json.loads(
                Path(options["mapping_file"]).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f"Could not read group-owner mapping: {error}") from error
        if not isinstance(mappings, list):
            raise CommandError("Mapping file must contain a JSON array.")

        with transaction.atomic():
            for item in mappings:
                if not isinstance(item, dict):
                    raise CommandError("Each mapping must be a JSON object.")
                conversation = Conversation.objects.select_for_update().filter(
                    conversation_id=item.get("conversation_id"),
                    conversation_type=Conversation.ConversationType.GROUP,
                ).first()
                if conversation is None:
                    raise CommandError("Mapped group does not exist.")
                member = ConversationMember.objects.select_for_update().filter(
                    conversation=conversation,
                    user_id=item.get("owner_id"),
                    is_active=True,
                ).first()
                if member is None:
                    raise CommandError("Owner must be an active member of the group.")
                if conversation.owner_id not in (None, member.user_id):
                    raise CommandError(
                        f"Group {conversation.conversation_id} already has another owner."
                    )
                if conversation.owner_id is None:
                    conversation.owner = member.user
                    conversation.version += 1
                    conversation.save(update_fields=["owner", "version"])
        self.stdout.write(self.style.SUCCESS(f"Assigned owners for {len(mappings)} group(s)."))
