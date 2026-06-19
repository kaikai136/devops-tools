from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("operations", "0002_move_models_to_feature_apps"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="AuthenticatorEntry",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                        ),
                        ("issuer", models.CharField(blank=True, max_length=200)),
                        ("account_name", models.CharField(blank=True, max_length=200)),
                        ("secret", models.CharField(max_length=200)),
                        ("digits", models.PositiveSmallIntegerField(default=6)),
                        ("period", models.PositiveSmallIntegerField(default=30)),
                        (
                            "algorithm",
                            models.CharField(
                                choices=[("SHA1", "SHA-1"), ("SHA256", "SHA-256"), ("SHA512", "SHA-512")],
                                default="SHA1",
                                max_length=10,
                            ),
                        ),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                    ],
                    options={
                        "db_table": "operations_authenticatorentry",
                        "ordering": ["issuer", "account_name", "id"],
                        "constraints": [
                            models.UniqueConstraint(
                                fields=("issuer", "account_name", "secret", "digits", "period", "algorithm"),
                                name="unique_authenticator_entry",
                            )
                        ],
                    },
                ),
            ],
        ),
    ]
