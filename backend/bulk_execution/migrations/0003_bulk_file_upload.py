from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bulk_execution", "0002_task_execution_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="bulkexecutiontask",
            name="remote_directory",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="bulkexecutiontask",
            name="upload_file",
            field=models.FileField(blank=True, upload_to="bulk_execution_uploads/"),
        ),
        migrations.AddField(
            model_name="bulkexecutiontask",
            name="upload_filename",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="bulkexecutiontask",
            name="upload_size",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="bulkexecutiontask",
            name="execution_type",
            field=models.CharField(
                choices=[("shell", "Shell"), ("playbook", "Playbook"), ("file_upload", "File upload")],
                default="shell",
                max_length=20,
            ),
        ),
    ]
