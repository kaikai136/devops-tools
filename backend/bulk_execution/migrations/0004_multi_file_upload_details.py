from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("bulk_execution", "0003_bulk_file_upload"),
    ]

    operations = [
        migrations.AddField(
            model_name="bulkexecutiontask",
            name="upload_overwrite",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="BulkExecutionUploadFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(blank=True, upload_to="bulk_execution_uploads/")),
                ("filename", models.CharField(max_length=255)),
                ("remote_path", models.CharField(max_length=700)),
                ("size", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "task",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="upload_files", to="bulk_execution.bulkexecutiontask"),
                ),
            ],
            options={
                "ordering": ["id"],
                "indexes": [models.Index(fields=["task"], name="bulk_upload_task_idx")],
            },
        ),
        migrations.CreateModel(
            name="BulkExecutionTransferItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("remote_path", models.CharField(max_length=700)),
                ("size", models.PositiveBigIntegerField(default=0)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("skipped", "Skipped"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("stdout", models.TextField(blank=True)),
                ("stderr", models.TextField(blank=True)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "result",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transfers", to="bulk_execution.bulkexecutionresult"),
                ),
                (
                    "task",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transfer_items", to="bulk_execution.bulkexecutiontask"),
                ),
                (
                    "upload_file",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transfers", to="bulk_execution.bulkexecutionuploadfile"),
                ),
            ],
            options={
                "ordering": ["id"],
                "indexes": [
                    models.Index(fields=["task", "status"], name="bulk_transfer_status_idx"),
                    models.Index(fields=["result"], name="bulk_transfer_result_idx"),
                ],
            },
        ),
    ]
