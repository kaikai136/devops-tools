from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("company_assets", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="companydevice",
            name="category",
            field=models.CharField(
                choices=[("固定资产", "固定资产"), ("耗材", "耗材")],
                default="固定资产",
                max_length=80,
            ),
        ),
        migrations.AlterField(
            model_name="companydevice",
            name="status",
            field=models.CharField(
                choices=[("using", "使用中"), ("idle", "闲置"), ("repair", "维修"), ("scrapped", "报废")],
                default="using",
                max_length=20,
            ),
        ),
    ]
