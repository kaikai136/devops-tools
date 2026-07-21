from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("host_management", "0010_remove_managedhost_unique_managed_host_private_ip"),
        ("web_terminal", "0004_terminalsession_rdp_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="terminalsession",
            name="client_ip",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="terminalsession",
            name="direct_mode",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="terminalsession",
            name="entrypoint",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="terminalsession",
            name="remote_username",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="terminalsession",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="terminal_sessions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="terminalsession",
            name="username",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.CreateModel(
            name="TerminalFileAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(max_length=150)),
                ("protocol", models.CharField(default="sftp", max_length=20)),
                (
                    "operation",
                    models.CharField(
                        choices=[
                            ("list", "List"),
                            ("read", "Read"),
                            ("write", "Write"),
                            ("mkdir", "Mkdir"),
                            ("remove", "Remove"),
                            ("rename", "Rename"),
                            ("stat", "Stat"),
                        ],
                        max_length=20,
                    ),
                ),
                ("path", models.TextField()),
                ("target_path", models.TextField(blank=True)),
                ("size", models.BigIntegerField(default=0)),
                (
                    "status",
                    models.CharField(choices=[("success", "Success"), ("failed", "Failed")], default="success", max_length=20),
                ),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "host",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="terminal_file_audits",
                        to="host_management.managedhost",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="file_audits",
                        to="web_terminal.terminalsession",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="terminal_file_audits",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["-created_at", "-id"], name="web_termina_created_96fbd0_idx"),
                    models.Index(fields=["host", "-created_at"], name="web_termina_host_id_c2932d_idx"),
                    models.Index(fields=["username", "-created_at"], name="web_termina_usernam_9ea6bf_idx"),
                    models.Index(fields=["operation", "-created_at"], name="web_termina_operati_16cfdc_idx"),
                    models.Index(fields=["protocol", "-created_at"], name="web_termina_protoco_5f49d2_idx"),
                    models.Index(fields=["status", "-created_at"], name="web_termina_status_6f082a_idx"),
                ],
            },
        ),
    ]
