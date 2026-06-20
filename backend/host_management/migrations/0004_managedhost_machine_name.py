from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("host_management", "0003_managedhost_verify_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="managedhost",
            name="machine_name",
            field=models.CharField(blank=True, max_length=160),
        ),
    ]
