from rest_framework import viewsets, generics
from rest_framework.response import Response
from django_filters import rest_framework as filters
from .models import Manga, Category
from .serializers import MangaSerializer, CategorySerializer


class MangaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    マンガ情報を取得するためのViewSet
    """
    queryset = Manga.objects.all()
    serializer_class = MangaSerializer
    lookup_field = 'id'


class PopularMangaListView(generics.ListAPIView):
    """
    カテゴリ別の人気マンガリストを取得するビュー
    """
    serializer_class = MangaSerializer
    
    def get_queryset(self):
        category = self.kwargs.get('category')
        
        # 'all' カテゴリの場合、すべてのマンガを返す
        if category == 'all':
            return Manga.objects.all().order_by('-rating')[:10]
        
        # 特定のカテゴリのマンガを返す
        return Manga.objects.filter(category=category).order_by('-rating')[:10]