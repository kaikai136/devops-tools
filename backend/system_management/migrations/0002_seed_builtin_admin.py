import os

from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.db import migrations


BUILTIN_ADMIN_USERNAME = "admin"
BUILTIN_ADMIN_EMAIL = "admin@ops.local"
BUILTIN_ADMIN_FIRST_NAME = "System Administrator"
BUILTIN_ADMIN_PASSWORD_ENV = "OPS_TOOL_ADMIN_PASSWORD"
BUILTIN_ADMIN_DEFAULT_PASSWORD = "Admin@123456"


def seed_builtin_admin(apps, _schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)

    admin_password = os.environ.get(BUILTIN_ADMIN_PASSWORD_ENV, "").strip() or BUILTIN_ADMIN_DEFAULT_PASSWORD
    password = make_password(admin_password)
    user, created = User.objects.get_or_create(
        username=BUILTIN_ADMIN_USERNAME,
        defaults={
            "email": BUILTIN_ADMIN_EMAIL,
            "first_name": BUILTIN_ADMIN_FIRST_NAME,
            "is_active": True,
            "is_staff": True,
            "is_superuser": True,
            "password": password,
        },
    )

    update_fields = []
    fixed_fields = {
        "email": BUILTIN_ADMIN_EMAIL,
        "first_name": BUILTIN_ADMIN_FIRST_NAME,
        "is_active": True,
        "is_staff": True,
        "is_superuser": True,
    }
    for field, value in fixed_fields.items():
        if getattr(user, field) != value:
            setattr(user, field, value)
            update_fields.append(field)

    if created:
        return

    user.password = password
    update_fields.append("password")

    if update_fields:
        user.save(update_fields=list(dict.fromkeys(update_fields)))


class Migration(migrations.Migration):

    dependencies = [
        ("system_management", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_builtin_admin, migrations.RunPython.noop),
    ]
