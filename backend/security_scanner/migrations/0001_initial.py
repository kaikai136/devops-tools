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
            name="SecurityScanTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("status", models.CharField(choices=[("queued", "排队中"), ("running", "扫描中"), ("completed", "已完成"), ("failed", "失败")], default="queued", max_length=20)),
                ("target_count", models.PositiveIntegerField(default=0)),
                ("completed_count", models.PositiveIntegerField(default=0)),
                ("critical_count", models.PositiveIntegerField(default=0)),
                ("high_count", models.PositiveIntegerField(default=0)),
                ("medium_count", models.PositiveIntegerField(default=0)),
                ("low_count", models.PositiveIntegerField(default=0)),
                ("info_count", models.PositiveIntegerField(default=0)),
                ("options", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="security_scan_tasks", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="SecurityScanHostResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("host_name", models.CharField(max_length=160)),
                ("host_ip", models.GenericIPAddressField(protocol="IPv4")),
                ("host_port", models.PositiveIntegerField(default=22)),
                ("login_user", models.CharField(blank=True, max_length=120)),
                ("os", models.CharField(blank=True, max_length=40)),
                ("system_type", models.CharField(blank=True, max_length=120)),
                ("status", models.CharField(choices=[("pending", "等待中"), ("running", "扫描中"), ("completed", "已完成"), ("failed", "失败")], default="pending", max_length=20)),
                ("system_info", models.JSONField(blank=True, default=dict)),
                ("open_ports", models.JSONField(blank=True, default=list)),
                ("package_count", models.PositiveIntegerField(default=0)),
                ("critical_count", models.PositiveIntegerField(default=0)),
                ("high_count", models.PositiveIntegerField(default=0)),
                ("medium_count", models.PositiveIntegerField(default=0)),
                ("low_count", models.PositiveIntegerField(default=0)),
                ("info_count", models.PositiveIntegerField(default=0)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("host", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="security_scan_results", to="host_management.managedhost")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="host_results", to="security_scanner.securityscantask")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="SecurityScanFinding",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(max_length=40)),
                ("severity", models.CharField(choices=[("critical", "严重"), ("high", "高危"), ("medium", "中危"), ("low", "低危"), ("info", "提示")], max_length=20)),
                ("title", models.CharField(max_length=260)),
                ("description", models.TextField(blank=True)),
                ("evidence", models.TextField(blank=True)),
                ("recommendation", models.TextField(blank=True)),
                ("cve_id", models.CharField(blank=True, max_length=80)),
                ("package_name", models.CharField(blank=True, max_length=160)),
                ("current_version", models.CharField(blank=True, max_length=160)),
                ("fixed_version", models.CharField(blank=True, max_length=160)),
                ("port", models.PositiveIntegerField(blank=True, null=True)),
                ("service", models.CharField(blank=True, max_length=120)),
                ("cvss", models.FloatField(blank=True, null=True)),
                ("cwe", models.CharField(blank=True, max_length=120)),
                ("source", models.CharField(blank=True, max_length=40)),
                ("references", models.JSONField(blank=True, default=list)),
                ("raw", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("host_result", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="findings", to="security_scanner.securityscanhostresult")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="findings", to="security_scanner.securityscantask")),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="VulnerabilityCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source", models.CharField(choices=[("osv", "OSV"), ("nvd", "NVD")], max_length=20)),
                ("cache_key", models.CharField(max_length=260)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("error", models.TextField(blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddIndex(model_name="securityscanfinding", index=models.Index(fields=["task", "severity"], name="secscan_find_task_sev_idx")),
        migrations.AddIndex(model_name="securityscanfinding", index=models.Index(fields=["cve_id"], name="secscan_find_cve_idx")),
        migrations.AddIndex(model_name="vulnerabilitycache", index=models.Index(fields=["source", "cache_key"], name="secscan_cache_src_key_idx")),
        migrations.AddConstraint(model_name="vulnerabilitycache", constraint=models.UniqueConstraint(fields=("source", "cache_key"), name="unique_vulnerability_cache_key")),
    ]
