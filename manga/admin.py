from django.contrib import admin
from .models import Manga, Category, EbookStore, ScrapingHistory, ScrapedManga

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Manga)
class MangaAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'author', 'category', 'free_chapters', 'free_books', 'rating')
    list_filter = ('category', 'rating')
    search_fields = ('title', 'author', 'description')
    readonly_fields = ('created_at', 'updated_at')


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
    list_display = ('title', 'author', 'category', 'rank', 'free_chapters', 'free_books', 'get_store', 'get_scraping_date')
    list_filter = ('category', 'scraping_history__store', 'scraping_history__scraping_date')
    search_fields = ('title', 'author')
    readonly_fields = ('created_at',)
    
    def get_store(self, obj):
        return obj.scraping_history.store.name
    get_store.short_description = '電子書籍ストア'
    get_store.admin_order_field = 'scraping_history__store__name'
    
    def get_scraping_date(self, obj):
        return obj.scraping_history.scraping_date
    get_scraping_date.short_description = 'スクレイピング日'
    get_scraping_date.admin_order_field = 'scraping_history__scraping_date'