from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("host_management", "0008_backfill_missing_host_creator"),
    ]

    operations = [
        migrations.AddField(
            model_name="managedhost",
            name="system_arch",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="managedhost",
            name="system_type",
            field=models.CharField(blank=True, max_length=80),
        ),
    ]
