from django.db import migrations, models


def seed_verify_status(apps, _schema_editor):
    ManagedHost = apps.get_model("host_management", "ManagedHost")
    ManagedHost.objects.filter(verified=True).update(verify_status="verified")
    ManagedHost.objects.filter(verified=False).update(verify_status="unverified")


class Migration(migrations.Migration):
    dependencies = [
        ("host_management", "0002_managedhost_login_password_managedhost_login_user_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="managedhost",
            name="verify_status",
            field=models.CharField(
                choices=[
                    ("unverified", "未验证"),
                    ("verified", "已验证"),
                    ("failed", "验证失败"),
                ],
                default="unverified",
                max_length=20,
            ),
        ),
        migrations.RunPython(seed_verify_status, migrations.RunPython.noop),
    ]
