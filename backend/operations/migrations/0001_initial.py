from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PasswordRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("project_name", models.CharField(blank=True, max_length=200)),
                ("password", models.CharField(max_length=200)),
                ("length", models.PositiveSmallIntegerField(default=16)),
                ("include_uppercase", models.BooleanField(default=True)),
                ("include_lowercase", models.BooleanField(default=True)),
                ("include_numbers", models.BooleanField(default=True)),
                ("include_symbols", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="PingHistoryRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target", models.CharField(max_length=255)),
                ("success_count", models.PositiveIntegerField(default=0)),
                ("failure_count", models.PositiveIntegerField(default=0)),
                ("loss_rate", models.PositiveSmallIntegerField(default=0)),
                ("average_response_time", models.PositiveIntegerField(blank=True, null=True)),
                ("min_response_time", models.PositiveIntegerField(blank=True, null=True)),
                ("max_response_time", models.PositiveIntegerField(blank=True, null=True)),
                ("jitter", models.PositiveIntegerField(blank=True, null=True)),
                ("total_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="AuthenticatorEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
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
                "ordering": ["issuer", "account_name", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("issuer", "account_name", "secret", "digits", "period", "algorithm"),
                        name="unique_authenticator_entry",
                    )
                ],
            },
        ),
    ]
