from rest_framework import serializers
from .models import Manga, Category

class CategorySerializer(serializers.ModelSerializer):
    """カテゴリのシリアライザ"""
    
    class Meta:
        model = Category
        fields = ['id', 'name']


class MangaSerializer(serializers.ModelSerializer):
    """マンガのシリアライザ"""
    # カテゴリーをIDのみで表示するため、StringRelatedFieldを使用
    categories = serializers.StringRelatedField(many=True)
    
    class Meta:
        model = Manga
        fields = [
            'id', 'title', 'isbn', 'author', 'cover_image', 
            'categories', 'description', 'first_book_title', 'rating',
            'free_chapters', 'free_books'
        ]
        read_only_fields = ['id']