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
                    name="PingHistoryRecord",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                        ),
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
                    options={
                        "db_table": "operations_pinghistoryrecord",
                        "ordering": ["-created_at"],
                    },
                ),
            ],
        ),
    ]
