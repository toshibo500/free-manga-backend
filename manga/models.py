from django.db import models

class Category(models.Model):
    """マンガのカテゴリモデル"""
    CATEGORY_CHOICES = [
        ('all', '全て'),
        ('shounen', '少年マンガ'),
        ('shoujo', '少女マンガ'),
        ('seinen', '青年マンガ'),
        ('josei', '女性マンガ'),
    ]
    
    id = models.CharField(max_length=20, primary_key=True, choices=CATEGORY_CHOICES)
    name = models.CharField(max_length=50)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = 'カテゴリ'
        verbose_name_plural = 'カテゴリ'


class Manga(models.Model):
    """マンガモデル"""
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=255)
    isbn = models.CharField(max_length=50, blank=True, null=True, verbose_name='ISBN')
    author = models.CharField(max_length=100)
    cover_image = models.URLField()
    categories = models.ManyToManyField(
        Category,
        related_name='mangas',
        verbose_name='カテゴリ'
    )
    description = models.TextField(blank=True, null=True)
    free_chapters = models.PositiveIntegerField(default=0, help_text='無料で読める話数')
    free_books = models.PositiveIntegerField(default=0, help_text='無料で読める冊数')
    rating = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title
    
    class Meta:
        verbose_name = 'マンガ'
        verbose_name_plural = 'マンガ'
        ordering = ['-rating', 'title']


class EbookStore(models.Model):
    """電子書籍ストアモデル"""
    name = models.CharField(max_length=100, verbose_name='ストア名')
    url = models.URLField(verbose_name='スクレイピング対象URL (総合カテゴリ)', 
                         help_text='この値は下位互換性のために残されています。新しいカテゴリURLはEbookStoreCategoryUrlを使用してください。')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='削除日時')
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = '電子書籍ストア'
        verbose_name_plural = '電子書籍ストア'
        ordering = ['name']


class EbookStoreCategoryUrl(models.Model):
    """電子書籍ストアのカテゴリごとのURL"""
    store = models.ForeignKey(EbookStore, on_delete=models.CASCADE, related_name='category_urls', verbose_name='電子書籍ストア')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='store_urls', verbose_name='カテゴリ')
    url = models.URLField(verbose_name='スクレイピング対象URL')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新日時')
    
    def __str__(self):
        return f"{self.store.name} - {self.category.name}"
    
    class Meta:
        verbose_name = 'ストアカテゴリURL'
        verbose_name_plural = 'ストアカテゴリURL'
        unique_together = ['store', 'category']
        ordering = ['store', 'category']


class ScrapingHistory(models.Model):
    """スクレイピング履歴モデル"""
    store = models.ForeignKey(EbookStore, on_delete=models.CASCADE, related_name='scraping_histories', verbose_name='電子書籍ストア')
    scraping_date = models.DateField(auto_now_add=True, verbose_name='スクレイピング日')
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='開始時間')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='終了時間')
    is_success = models.BooleanField(default=False, verbose_name='成功フラグ')
    error_message = models.TextField(null=True, blank=True, verbose_name='エラーメッセージ')
    
    def __str__(self):
        return f"{self.store.name} - {self.scraping_date}"
    
    class Meta:
        verbose_name = 'スクレイピング履歴'
        verbose_name_plural = 'スクレイピング履歴'
        ordering = ['-scraping_date', '-started_at']
        unique_together = ['store', 'scraping_date']


class ScrapedManga(models.Model):
    """スクレイピングしたマンガデータモデル"""
    scraping_history = models.ForeignKey('ScrapingHistory', on_delete=models.CASCADE, related_name='scraped_mangas', verbose_name='スクレイピング履歴')
    manga = models.ForeignKey('Manga', on_delete=models.PROTECT, related_name='scraped_mangas', verbose_name='マンガ')
    free_chapters = models.IntegerField(verbose_name='無料話数')
    free_books = models.IntegerField(verbose_name='無料冊数')
    rank = models.PositiveIntegerField(verbose_name='ランキング順位')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
    
    def __str__(self):
        return f"{self.manga.title} (Rank: {self.rank})"
    
    class Meta:
        verbose_name = 'スクレイピングマンガデータ'
        verbose_name_plural = 'スクレイピングマンガデータ'
        ordering = ['scraping_history', 'rank']
        unique_together = ['scraping_history', 'manga']
