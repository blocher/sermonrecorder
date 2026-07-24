from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sermons", "0011_alter_studyartifact_kind"),
    ]

    operations = [
        migrations.AlterField(
            model_name="studyartifact",
            name="kind",
            field=models.CharField(
                choices=[
                    ("short_summary", "Short summary"),
                    ("long_summary", "Long summary"),
                    ("outline", "Outline"),
                    ("practical_next_steps", "Practical next steps"),
                    ("call_to_action", "One next action"),
                    ("quotations", "Quotations"),
                    ("adult_discussion_questions", "Adult discussion questions"),
                    ("kids_discussion_questions", "Kids discussion questions"),
                    ("sermon_feedback", "Sermon feedback"),
                    ("hymn", "Hymn"),
                    ("hymn_tune_suggestions", "Hymn tune suggestions"),
                    ("quiz", "Quiz"),
                ],
                max_length=40,
            ),
        ),
    ]
