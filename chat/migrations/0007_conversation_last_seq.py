from django.db import migrations, models
from django.db.models import Max


def populate_conversation_sequences(apps, schema_editor):
    Conversation = apps.get_model("chat", "Conversation")
    Message = apps.get_model("chat", "Message")
    database = schema_editor.connection.alias

    last_sequences = (
        Message.objects.using(database)
        .order_by()
        .values("conversation_id")
        .annotate(last_seq=Max("seq"))
        .iterator()
    )
    for item in last_sequences:
        Conversation.objects.using(database).filter(
            conversation_id=item["conversation_id"]
        ).update(last_seq=item["last_seq"])


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0006_user_bio_user_sex_user_short_bio_user_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="conversation",
            name="last_seq",
            field=models.BigIntegerField(db_column="last_seq", default=0),
        ),
        migrations.RunPython(
            populate_conversation_sequences,
            migrations.RunPython.noop,
        ),
    ]
