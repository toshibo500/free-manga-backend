from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('manga', '0003_scrapedmanga_scrapinghistory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scrapedmanga',
            name='author',
            field=models.CharField(max_length=255, verbose_name='著者'),
        ),
    ]