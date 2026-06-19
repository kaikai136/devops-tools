from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("operations", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="AuthenticatorEntry"),
                migrations.DeleteModel(name="PasswordRecord"),
                migrations.DeleteModel(name="PingHistoryRecord"),
            ],
        ),
    ]
