from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_userprofile_totp_setup_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="session_audit_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
