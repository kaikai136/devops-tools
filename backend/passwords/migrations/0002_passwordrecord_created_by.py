from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

BUILTIN_ADMIN_USERNAME = "admin"


def assign_existing_records_to_admin(apps, _schema_editor):
    User = apps.get_model("auth", "User")
    PasswordRecord = apps.get_model("passwords", "PasswordRecord")
    admin = User.objects.filter(username=BUILTIN_ADMIN_USERNAME).first() or User.objects.order_by("id").first()
    if not admin and PasswordRecord.objects.filter(created_by__isnull=True).exists():
        admin = User.objects.create(
            username=BUILTIN_ADMIN_USERNAME,
            email="admin@ops.local",
            first_name="System Administrator",
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
    if admin:
        PasswordRecord.objects.filter(created_by__isnull=True).update(created_by=admin)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("passwords", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="passwordrecord",
            name="created_by",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="password_records",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(assign_existing_records_to_admin, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="passwordrecord",
            name="created_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="password_records",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
