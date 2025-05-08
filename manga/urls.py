from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import MangaViewSet, PopularMangaListView

router = DefaultRouter()
router.register('manga', MangaViewSet, basename='manga')

urlpatterns = [
    path('manga/popular-books/<str:category>/', PopularMangaListView.as_view(), name='popular-manga'),
] + router.urls