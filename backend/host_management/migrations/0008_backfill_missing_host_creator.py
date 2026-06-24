from django.conf import settings
from django.db import migrations


def backfill_missing_host_creator(apps, _schema_editor):
    ManagedHost = apps.get_model("host_management", "ManagedHost")
    User = apps.get_model(settings.AUTH_USER_MODEL)
    fallback_user = User.objects.filter(username="admin").first() or User.objects.order_by("id").first()
    if not fallback_user:
        return
    ManagedHost.objects.filter(created_by__isnull=True).update(created_by=fallback_user)


class Migration(migrations.Migration):

    dependencies = [
        ("host_management", "0007_managedhost_updated_at_backfill_metadata"),
    ]

    operations = [
        migrations.RunPython(backfill_missing_host_creator, migrations.RunPython.noop),
    ]
