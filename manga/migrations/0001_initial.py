from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.CharField(choices=[('all', '全て'), ('shounen', '少年マンガ'), ('shoujo', '少女マンガ'), ('seinen', '青年マンガ'), ('josei', '女性マンガ')], max_length=20, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=50)),
            ],
            options={
                "verbose_name": "カテゴリ",
                "verbose_name_plural": "カテゴリ",
            },
        ),
        migrations.CreateModel(
            name="EbookStore",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="ストア名")),
                ("url", models.URLField(help_text="この値は下位互換性のために残されています。新しいカテゴリURLはEbookStoreCategoryUrlを使用してください。", verbose_name="スクレイピング対象URL (総合カテゴリ)")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="作成日時")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新日時")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="削除日時")),
            ],
            options={
                "verbose_name": "電子書籍ストア",
                "verbose_name_plural": "電子書籍ストア",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Manga",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=255)),
                ("author", models.CharField(max_length=100)),
                ("cover_image", models.URLField()),
                ("free_chapters", models.IntegerField()),
                ("free_books", models.IntegerField()),
                ("description", models.TextField(blank=True, null=True)),
                ("rating", models.DecimalField(decimal_places=1, default=0.0, max_digits=3)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "マンガ",
                "verbose_name_plural": "マンガ",
                "ordering": ["-rating", "title"],
            },
        ),
        migrations.CreateModel(
            name="ScrapingHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scraping_date", models.DateField(auto_now_add=True, verbose_name="スクレイピング日")),
                ("started_at", models.DateTimeField(auto_now_add=True, verbose_name="開始時間")),
                ("finished_at", models.DateTimeField(blank=True, null=True, verbose_name="終了時間")),
                ("is_success", models.BooleanField(default=False, verbose_name="成功フラグ")),
                ("error_message", models.TextField(blank=True, null=True, verbose_name="エラーメッセージ")),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scraping_histories",
                        to="manga.ebookstore",
                        verbose_name="電子書籍ストア",
                    ),
                ),
            ],
            options={
                "verbose_name": "スクレイピング履歴",
                "verbose_name_plural": "スクレイピング履歴",
                "ordering": ["-scraping_date", "-started_at"],
                "unique_together": {("store", "scraping_date")},
            },
        ),
        migrations.CreateModel(
            name="ScrapedManga",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("free_chapters", models.IntegerField(verbose_name="無料話数")),
                ("free_books", models.IntegerField(verbose_name="無料冊数")),
                ("rank", models.PositiveIntegerField(verbose_name="ランキング順位")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="作成日時")),
                (
                    "manga",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="scraped_mangas",
                        to="manga.manga",
                        verbose_name="マンガ",
                    ),
                ),
                (
                    "scraping_history",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scraped_mangas",
                        to="manga.scrapinghistory",
                        verbose_name="スクレイピング履歴",
                    ),
                ),
            ],
            options={
                "verbose_name": "スクレイピングマンガデータ",
                "verbose_name_plural": "スクレイピングマンガデータ",
                "ordering": ["scraping_history", "rank"],
                "unique_together": {("scraping_history", "manga")},
            },
        ),
        migrations.CreateModel(
            name="EbookStoreCategoryUrl",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("url", models.URLField(verbose_name="スクレイピング対象URL")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="作成日時")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新日時")),
                (
                    "category",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="store_urls",
                        to="manga.category",
                        verbose_name="カテゴリ",
                    ),
                ),
                (
                    "store",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="category_urls",
                        to="manga.ebookstore",
                        verbose_name="電子書籍ストア",
                    ),
                ),
            ],
            options={
                "verbose_name": "ストアカテゴリURL",
                "verbose_name_plural": "ストアカテゴリURL",
                "ordering": ["store", "category"],
                "unique_together": {("store", "category")},
            },
        ),
        migrations.AddField(
            model_name="manga",
            name="categories",
            field=models.ManyToManyField(related_name="mangas", to="manga.category", verbose_name="カテゴリ"),
        ),
    ]
