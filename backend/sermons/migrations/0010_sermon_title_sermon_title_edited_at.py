from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sermons", "0009_alter_studyartifact_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="sermon",
            name="title",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="sermon",
            name="title_edited_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
