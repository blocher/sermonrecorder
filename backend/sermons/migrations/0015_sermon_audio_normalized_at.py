from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sermons", "0014_sermon_consider_window"),
    ]

    operations = [
        migrations.AddField(
            model_name="sermon",
            name="audio_normalized_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
