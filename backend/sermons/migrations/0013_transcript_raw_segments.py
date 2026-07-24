from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sermons", "0012_alter_studyartifact_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="transcript",
            name="raw_segments",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
