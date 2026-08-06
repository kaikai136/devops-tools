from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bulk_execution", "0004_multi_file_upload_details"),
    ]

    operations = [
        migrations.AddField(
            model_name="bulkexecutiontask",
            name="log_output",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="bulkexecutiontask",
            name="log_output_truncated",
            field=models.BooleanField(default=False),
        ),
    ]
