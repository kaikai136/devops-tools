from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("host_management", "0008_backfill_missing_host_creator"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApplicationSource",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("source_type", models.CharField(choices=[("builtin", "Builtin"), ("remote", "Remote")], default="remote", max_length=20)),
                ("url", models.URLField(blank=True)),
                ("enabled", models.BooleanField(default=True)),
                ("cached_payload", models.JSONField(blank=True, default=list)),
                ("last_synced_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="ApplicationDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("app_id", models.CharField(max_length=120)),
                ("name", models.CharField(max_length=160)),
                ("category", models.CharField(max_length=80)),
                ("description", models.TextField(blank=True)),
                ("icon", models.CharField(blank=True, max_length=200)),
                ("version", models.CharField(default="1.0.0", max_length=80)),
                ("source", models.CharField(default="remote", max_length=80)),
                ("install_mode", models.CharField(default="compose", max_length=40)),
                ("requirements", models.JSONField(blank=True, default=dict)),
                ("config_schema", models.JSONField(blank=True, default=list)),
                ("manifest", models.JSONField(blank=True, default=dict)),
                ("capabilities", models.JSONField(blank=True, default=list)),
                ("checksum", models.CharField(blank=True, max_length=128)),
                ("enabled", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["source", "category", "name"]},
        ),
        migrations.CreateModel(
            name="ApplicationInstallation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("app_id", models.CharField(max_length=120)),
                ("target_key", models.CharField(max_length=80)),
                ("target_type", models.CharField(choices=[("local", "Local"), ("managed_host", "Managed host")], max_length=20)),
                ("version", models.CharField(blank=True, max_length=80)),
                ("status", models.CharField(default="unknown", max_length=40)),
                ("containers", models.JSONField(blank=True, default=list)),
                ("ports", models.JSONField(blank=True, default=list)),
                ("images", models.JSONField(blank=True, default=list)),
                ("last_probed_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("target_host", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="application_installations", to="host_management.managedhost")),
            ],
            options={"ordering": ["target_key", "app_id"]},
        ),
        migrations.CreateModel(
            name="ApplicationTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("app_id", models.CharField(max_length=120)),
                ("app_name", models.CharField(max_length=160)),
                ("action", models.CharField(choices=[("install", "Install"), ("update", "Update"), ("uninstall", "Uninstall"), ("start", "Start"), ("stop", "Stop"), ("restart", "Restart")], max_length=20)),
                ("target_key", models.CharField(max_length=80)),
                ("target_type", models.CharField(choices=[("local", "Local"), ("managed_host", "Managed host")], max_length=20)),
                ("status", models.CharField(choices=[("queued", "Queued"), ("running", "Running"), ("success", "Success"), ("failed", "Failed"), ("canceled", "Canceled"), ("unknown", "Unknown")], default="queued", max_length=20)),
                ("cancel_requested", models.BooleanField(default=False)),
                ("version", models.CharField(blank=True, max_length=80)),
                ("config", models.JSONField(blank=True, default=dict)),
                ("plan", models.TextField(blank=True)),
                ("plan_digest", models.CharField(blank=True, max_length=128)),
                ("log_output", models.TextField(blank=True)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="application_market_tasks", to=settings.AUTH_USER_MODEL)),
                ("target_host", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="application_tasks", to="host_management.managedhost")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddConstraint("ApplicationDefinition", models.UniqueConstraint(fields=("source", "app_id"), name="unique_market_definition_source_app")),
        migrations.AddConstraint("ApplicationInstallation", models.UniqueConstraint(fields=("target_key", "app_id"), name="unique_market_installation_target_app")),
        migrations.AddIndex("ApplicationTask", models.Index(fields=["status", "-created_at"], name="market_task_status_idx")),
        migrations.AddIndex("ApplicationTask", models.Index(fields=["target_key", "app_id"], name="market_task_target_app_idx")),
    ]
