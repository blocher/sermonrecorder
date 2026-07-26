from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sermons", "0017_sermon_playback_audio"),
    ]

    operations = [
        migrations.AddField(
            model_name="sermon",
            name="transcription_audio_source",
            field=models.CharField(
                choices=[
                    ("playback", "Processed playback"),
                    ("original", "Original upload"),
                ],
                default="playback",
                max_length=20,
            ),
        ),
    ]
