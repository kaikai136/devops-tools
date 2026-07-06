from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="HostGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="host_management.hostgroup",
                    ),
                ),
            ],
            options={"ordering": ["sort_order", "id"]},
        ),
        migrations.CreateModel(
            name="ManagedHost",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160)),
                ("public_ip", models.GenericIPAddressField(blank=True, null=True, protocol="IPv4")),
                ("private_ip", models.GenericIPAddressField(protocol="IPv4")),
                ("cpu", models.PositiveSmallIntegerField(default=2)),
                ("memory", models.PositiveSmallIntegerField(default=4)),
                (
                    "os",
                    models.CharField(
                        choices=[("ubuntu", "Ubuntu"), ("centos", "CentOS"), ("debian", "Debian")],
                        default="centos",
                        max_length=20,
                    ),
                ),
                ("verified", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="hosts",
                        to="host_management.hostgroup",
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.AddConstraint(
            model_name="hostgroup",
            constraint=models.UniqueConstraint(fields=("parent", "name"), name="unique_host_group_name_per_parent"),
        ),
        migrations.AddConstraint(
            model_name="managedhost",
            constraint=models.UniqueConstraint(fields=("private_ip",), name="unique_managed_host_private_ip"),
        ),
    ]
