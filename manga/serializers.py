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
    category = serializers.StringRelatedField()
    
    class Meta:
        model = Manga
        fields = [
            'id', 'title', 'author', 'cover_image', 
            'free_chapters', 'free_books', 'category', 
            'description', 'rating'
        ]
        read_only_fields = ['id']