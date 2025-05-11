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
            'id', 'title', 'author', 'cover_image', 
            'categories', 'description', 'rating'
        ]
        read_only_fields = ['id']