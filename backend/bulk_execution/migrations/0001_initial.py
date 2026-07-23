from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("host_management", "0010_remove_managedhost_unique_managed_host_private_ip"),
    ]

    operations = [
        migrations.CreateModel(
            name="BulkExecutionTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("command", models.TextField()),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed"), ("canceled", "Canceled")], default="queued", max_length=20)),
                ("cancel_requested", models.BooleanField(default=False)),
                ("target_count", models.PositiveIntegerField(default=0)),
                ("completed_count", models.PositiveIntegerField(default=0)),
                ("success_count", models.PositiveIntegerField(default=0)),
                ("failed_count", models.PositiveIntegerField(default=0)),
                ("skipped_count", models.PositiveIntegerField(default=0)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bulk_execution_tasks", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="BulkExecutionResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("inventory_name", models.CharField(max_length=80)),
                ("host_name", models.CharField(max_length=160)),
                ("host_ip", models.GenericIPAddressField(protocol="IPv4")),
                ("host_port", models.PositiveIntegerField(default=22)),
                ("login_user", models.CharField(blank=True, max_length=120)),
                ("os", models.CharField(blank=True, max_length=40)),
                ("system_type", models.CharField(blank=True, max_length=120)),
                ("system_arch", models.CharField(blank=True, max_length=80)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("running", "Running"), ("success", "Success"), ("failed", "Failed"), ("skipped", "Skipped")], default="pending", max_length=20)),
                ("stdout", models.TextField(blank=True)),
                ("stderr", models.TextField(blank=True)),
                ("exit_code", models.IntegerField(blank=True, null=True)),
                ("error", models.TextField(blank=True)),
                ("output_truncated", models.BooleanField(default=False)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("host", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="bulk_execution_results", to="host_management.managedhost")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="results", to="bulk_execution.bulkexecutiontask")),
            ],
            options={
                "ordering": ["id"],
            },
        ),
        migrations.AddIndex(model_name="bulkexecutiontask", index=models.Index(fields=["status", "-created_at"], name="bulk_task_status_idx")),
        migrations.AddIndex(model_name="bulkexecutiontask", index=models.Index(fields=["-created_at"], name="bulk_task_created_idx")),
        migrations.AddIndex(model_name="bulkexecutionresult", index=models.Index(fields=["task", "status"], name="bulk_result_status_idx")),
        migrations.AddIndex(model_name="bulkexecutionresult", index=models.Index(fields=["host"], name="bulk_result_host_idx")),
    ]
