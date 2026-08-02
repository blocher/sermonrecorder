from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sermons", "0020_alter_sermon_transcription_audio_source_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="transcript",
            name="display_text",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="transcript",
            name="display_segments",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
