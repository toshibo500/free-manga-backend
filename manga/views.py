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
    
    クエリパラメータ:
    - count: 返すマンガの件数（デフォルト: 10、最大: 100）
    - offset: 開始位置（デフォルト: 0）
    """
    serializer_class = MangaSerializer
    pagination_class = None  # デフォルトのページネーションを無効化
    
    def get_queryset(self):
        category = self.kwargs.get('category')
        
        # リクエストからcount（件数）とoffset（開始位置）を取得
        count = self.request.query_params.get('count', 100)
        offset = self.request.query_params.get('offset', 0)
        
        # 文字列から整数に変換
        try:
            count = int(count)
            if count <= 0:
                count = 10
            elif count > 100:
                count = 100  # 最大100件まで許容
        except (TypeError, ValueError):
            count = 10
            
        try:
            offset = int(offset)
            if offset < 0:
                offset = 0
        except (TypeError, ValueError):
            offset = 0
        
        # 'all' カテゴリの場合、すべてのマンガを返す
        if category == 'all':
            queryset = Manga.objects.all().order_by('-rating')
        else:
            # 特定のカテゴリのマンガを返す
            queryset = Manga.objects.filter(categories__id=category).order_by('-rating')
        
        # offset と count を適用
        return queryset[offset:offset+count]