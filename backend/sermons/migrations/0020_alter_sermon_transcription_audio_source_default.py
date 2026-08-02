from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sermons", "0019_related_sources_and_doctrinal_review"),
    ]

    operations = [
        migrations.AlterField(
            model_name="sermon",
            name="transcription_audio_source",
            field=models.CharField(
                choices=[
                    ("playback", "Isolated playback"),
                    ("original", "Original upload"),
                ],
                default="original",
                max_length=20,
            ),
        ),
    ]
