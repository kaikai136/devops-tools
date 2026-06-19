from django.db import migrations, models
import django.db.models.deletion


def seed_host_management(apps, _schema_editor):
    HostGroup = apps.get_model("host_management", "HostGroup")
    ManagedHost = apps.get_model("host_management", "ManagedHost")

    tencent = HostGroup.objects.create(name="腾讯云", sort_order=10)
    aliyun = HostGroup.objects.create(name="阿里云", sort_order=20)
    core = HostGroup.objects.create(name="核心服务", parent=aliyun, sort_order=10)
    user = HostGroup.objects.create(name="用户服务", parent=aliyun, sort_order=20)
    order = HostGroup.objects.create(name="订单服务", parent=aliyun, sort_order=30)

    ManagedHost.objects.bulk_create(
        [
            ManagedHost(name="web-04", group=tencent, private_ip="172.21.0.12", cpu=2, memory=4, os="ubuntu"),
            ManagedHost(name="web-03", group=tencent, public_ip="121.199.4.33", private_ip="172.21.0.10", cpu=28, memory=224, os="centos"),
            ManagedHost(name="web-02", group=tencent, private_ip="172.21.0.11", cpu=2, memory=4, os="centos"),
            ManagedHost(name="api-01", group=tencent, private_ip="172.21.0.20", cpu=4, memory=8, os="debian", verified=True),
            ManagedHost(name="工具前台_测试", group=aliyun, private_ip="172.17.0.1", cpu=1, memory=4, os="centos", verified=True),
            ManagedHost(name="core-api-01", group=core, private_ip="172.17.1.10", cpu=4, memory=8, os="centos"),
            ManagedHost(name="user-api-01", group=user, private_ip="172.17.2.10", cpu=2, memory=4, os="ubuntu"),
            ManagedHost(name="order-api-01", group=order, private_ip="172.17.3.10", cpu=2, memory=4, os="debian"),
        ]
    )


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
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="children", to="host_management.hostgroup"),
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
                ("os", models.CharField(choices=[("ubuntu", "Ubuntu"), ("centos", "CentOS"), ("debian", "Debian")], default="centos", max_length=20)),
                ("verified", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("group", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="hosts", to="host_management.hostgroup")),
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
        migrations.RunPython(seed_host_management, migrations.RunPython.noop),
    ]
