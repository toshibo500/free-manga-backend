from django.contrib import admin
from .models import Manga, Category, EbookStore, ScrapingHistory, ScrapedManga, EbookStoreCategoryUrl

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Manga)
class MangaAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'author', 'first_book_title', 'get_categories', 'rating')
    list_filter = ('categories', 'rating')
    search_fields = ('title', 'author', 'first_book_title', 'description')
    readonly_fields = ('created_at', 'updated_at')

    def get_categories(self, obj):
        return ", ".join([c.name for c in obj.categories.all()])
    get_categories.short_description = 'カテゴリ'


@admin.register(EbookStore)
class EbookStoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'url', 'created_at', 'updated_at', 'deleted_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ScrapingHistory)
class ScrapingHistoryAdmin(admin.ModelAdmin):
    list_display = ('store', 'scraping_date', 'started_at', 'finished_at', 'is_success')
    list_filter = ('store', 'scraping_date', 'is_success')
    search_fields = ('store__name', 'error_message')
    readonly_fields = ('scraping_date', 'started_at')


@admin.register(ScrapedManga)
class ScrapedMangaAdmin(admin.ModelAdmin):
    list_display = ('get_title', 'get_author', 'get_categories', 'rank', 'free_chapters', 'free_books', 'get_store', 'get_scraping_date')
    list_filter = ('manga__categories', 'scraping_history__store', 'scraping_history__scraping_date')
    search_fields = ('manga__title', 'manga__author')
    readonly_fields = ('created_at',)
    
    def get_title(self, obj):
        return obj.manga.title
    get_title.short_description = 'タイトル'
    
    def get_author(self, obj):
        return obj.manga.author
    get_author.short_description = '著者'
    
    def get_categories(self, obj):
        return ", ".join([c.name for c in obj.manga.categories.all()])
    get_categories.short_description = 'カテゴリ'
    
    def get_store(self, obj):
        return obj.scraping_history.store.name
    get_store.short_description = '電子書籍ストア'
    get_store.admin_order_field = 'scraping_history__store__name'
    
    def get_scraping_date(self, obj):
        return obj.scraping_history.scraping_date
    get_scraping_date.short_description = 'スクレイピング日'
    get_scraping_date.admin_order_field = 'scraping_history__scraping_date'


@admin.register(EbookStoreCategoryUrl)
class EbookStoreCategoryUrlAdmin(admin.ModelAdmin):
    list_display = ('store', 'category', 'url', 'created_at', 'updated_at')
    list_filter = ('store', 'category')
    search_fields = ('store__name', 'category__name', 'url')
    readonly_fields = ('created_at', 'updated_at')