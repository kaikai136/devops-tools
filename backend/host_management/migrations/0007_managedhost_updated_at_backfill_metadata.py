from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_host_metadata(apps, _schema_editor):
    ManagedHost = apps.get_model("host_management", "ManagedHost")
    User = apps.get_model(settings.AUTH_USER_MODEL)
    fallback_user = User.objects.filter(username="admin").first() or User.objects.order_by("id").first()
    now = timezone.now()

    for host in ManagedHost.objects.all():
        update_fields = []
        if host.created_at is None:
            host.created_at = now
            update_fields.append("created_at")
        if host.created_by_id is None and fallback_user:
            host.created_by = fallback_user
            update_fields.append("created_by")
        if host.updated_at is None and (host.verified or host.verify_status == "failed"):
            host.updated_at = host.created_at or now
            update_fields.append("updated_at")
        if update_fields:
            host.save(update_fields=update_fields)


class Migration(migrations.Migration):

    dependencies = [
        ("host_management", "0006_managedhost_created_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="managedhost",
            name="updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_host_metadata, migrations.RunPython.noop),
    ]
