from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bulk_execution", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="bulkexecutiontask",
            name="execution_type",
            field=models.CharField(
                choices=[("shell", "Shell"), ("playbook", "Playbook")],
                default="shell",
                max_length=20,
            ),
        ),
    ]
