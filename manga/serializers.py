from rest_framework import serializers
from .models import Manga, Category, EbookStore, MangaEbookStore
from drf_yasg.utils import swagger_serializer_method

class CategorySerializer(serializers.ModelSerializer):
    """カテゴリのシリアライザ"""
    
    class Meta:
        model = Category
        fields = ['id', 'name']


class EbookStoreDetailSerializer(serializers.Serializer):
    """電子書籍ストア詳細情報のシリアライザ"""
    ebookstore_name = serializers.CharField()
    manga_detail_url = serializers.URLField()
    free_chapters = serializers.IntegerField()
    free_books = serializers.IntegerField()


class MangaSerializer(serializers.ModelSerializer):
    """マンガのシリアライザ"""
    # カテゴリーをIDのみで表示するため、StringRelatedFieldを使用
    categories = serializers.StringRelatedField(many=True)
    # 電子書籍ストア情報
    ebookstores = serializers.SerializerMethodField()
    
    class Meta:
        model = Manga
        fields = [
            'id', 'title', 'isbn', 'author', 'cover_image', 
            'categories', 'description', 'first_book_title', 'rating',
            'free_chapters', 'free_books', 'ebookstores'
        ]
        read_only_fields = ['id']
    
    @swagger_serializer_method(serializer_or_field=EbookStoreDetailSerializer(many=True))
    def get_ebookstores(self, obj):
        detail_urls = MangaEbookStore.objects.filter(manga=obj).select_related('ebookstore')
        return [
            {
                'ebookstore_name': d.ebookstore.name,
                'manga_detail_url': d.url,
                'free_chapters': d.free_chapters,
                'free_books': d.free_books
            }
            for d in detail_urls
        ]