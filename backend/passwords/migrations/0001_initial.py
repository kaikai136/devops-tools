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
                    name="PasswordRecord",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                        ),
                        ("project_name", models.CharField(blank=True, max_length=200)),
                        ("password", models.CharField(max_length=200)),
                        ("length", models.PositiveSmallIntegerField(default=16)),
                        ("include_uppercase", models.BooleanField(default=True)),
                        ("include_lowercase", models.BooleanField(default=True)),
                        ("include_numbers", models.BooleanField(default=True)),
                        ("include_symbols", models.BooleanField(default=False)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                    ],
                    options={
                        "db_table": "operations_passwordrecord",
                        "ordering": ["-created_at"],
                    },
                ),
            ],
        ),
    ]
