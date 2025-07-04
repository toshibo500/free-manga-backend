"""
基底スクレイパークラス
すべての電子書籍ストア用スクレイパーはこのクラスを継承します
"""
import logging
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from django.db import transaction
from manga.models import Category, ScrapingHistory, ScrapedManga, EbookStore, MangaEbookStore
from scripts.utils import get_or_create_manga

logger = logging.getLogger(__name__)

class BaseStoreScraper(ABC):
    """
    基底スクレイパークラス
    すべてのストアスクレイパーはこのクラスを継承する必要があります
    """
    
    def __init__(self, store_id):
        """
        初期化
        
        Args:
            store_id (int): 電子書籍ストアのID
        """
        self.store = None
        self.history = None
        
        try:
            self.store = EbookStore.objects.get(id=store_id)
        except EbookStore.DoesNotExist:
            logger.error(f"ID: {store_id}の電子書籍ストアが見つかりません")
            raise
        
        logger.info(f"スクレイパー初期化: {self.store.name}")
    
    def run(self):
        """
        スクレイピングを実行します
        """
        # 既にscraping_history属性がセットされていればそれを使う
        if hasattr(self, 'scraping_history') and self.scraping_history:
            self.history = self.scraping_history
        else:
            self.history = self._create_history()
        try:
            # スクレイピングを実行
            logger.info(f"{self.store.name} のスクレイピングを開始します")
            manga_data_list = self._scrape()
            self._save_data(manga_data_list)
            self._update_history_success()
            logger.info(f"{self.store.name} のスクレイピングが正常に完了しました")
            return True
        except Exception as e:
            error_message = f"スクレイピング中にエラーが発生しました: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_message)
            self._update_history_failure(error_message)
            return False
    
    def _create_history(self):
        """スクレイピング履歴を作成"""
        return ScrapingHistory.objects.create(
            store=self.store,
            is_success=False  # 最初はFalseで作成し、成功時に更新
        )
    
    def _update_history_success(self):
        """スクレイピング履歴を成功として更新"""
        self.history.is_success = True
        self.history.finished_at = datetime.now()
        self.history.save()
    
    def _update_history_failure(self, error_message):
        """スクレイピング履歴を失敗として更新"""
        self.history.is_success = False
        self.history.error_message = error_message
        self.history.finished_at = datetime.now()
        self.history.save()
    
    def _save_data(self, manga_data_list):
        """
        スクレイピングしたマンガデータを保存
        各項目ごとに独立してトランザクションを実行し、一部のデータが失敗しても他のデータが保存されるようにする
        
        Args:
            manga_data_list (list): マンガデータのリスト。各要素は以下のキーを含む辞書:
                - title (str): マンガタイトル
                - author (str): 著者名
                - first_book_title (str, optional): 第1巻タイトル
                - free_chapters (int): 無料話数
                - free_books (int): 無料冊数
                - rank (int): ランキング順位
                - category_id (str): カテゴリID
                または
                - manga (Manga): 既に作成済みのMangaオブジェクト（後方互換性のため）
        """
        created_count = 0
        for i, manga_data in enumerate(manga_data_list):
            try:
                with transaction.atomic():
                    category_id = manga_data.get('category_id', 'all')
                    category = Category.objects.get(id=category_id)
                    
                    # Mangaオブジェクトの取得または作成
                    if 'manga' in manga_data:
                        # 既にMangaオブジェクトが作成済みの場合（後方互換性）
                        manga = manga_data['manga']
                    else:
                        # 生データからMangaオブジェクトを作成
                        title = manga_data['title']
                        author = manga_data['author']
                        first_book_title = manga_data.get('first_book_title', '')
                        categories = [category]
                        
                        manga, _ = get_or_create_manga(
                            title=title,
                            author=author,
                            categories=categories,
                            first_book_title=first_book_title
                        )
                        
                        if not manga:
                            logger.warning(f"マンガの作成に失敗しました: '{title}' (rank: {manga_data.get('rank', i+1)})")
                            continue
                    
                    ScrapedManga.objects.update_or_create(
                        scraping_history=self.history,
                        manga=manga,
                        defaults={
                            'free_chapters': manga_data['free_chapters'],
                            'free_books': manga_data['free_books'],
                            'rank': manga_data['rank']
                        }
                    )
                    
                    # 詳細URLがある場合は保存
                    detail_url = manga_data.get('detail_url')
                    free_chapters = manga_data.get('free_chapters', 0)
                    free_books = manga_data.get('free_books', 0)
                    if detail_url:
                        MangaEbookStore.objects.update_or_create(
                            manga=manga,
                            ebookstore=self.store,
                            defaults={
                                'url': detail_url,
                                'free_chapters': free_chapters,
                                'free_books': free_books
                            }
                        )
                        logger.debug(f"詳細URL・無料話数・無料巻数保存: {manga.title} -> {detail_url}, {free_chapters}, {free_books}")
                    else:
                        # URLがない場合も無料話数・無料巻数を更新
                        MangaEbookStore.objects.update_or_create(
                            manga=manga,
                            ebookstore=self.store,
                            defaults={
                                'free_chapters': free_chapters,
                                'free_books': free_books
                            }
                        )
                    
                    created_count += 1
            except Exception as e:
                logger.warning(f"マンガデータの保存中にエラーが発生しました (rank: {i+1}): {str(e)}")
        logger.info(f"{created_count}件のマンガデータを保存しました")
    
    @abstractmethod
    def _scrape(self):
        """
        実際のスクレイピング処理を行うメソッド
        子クラスでオーバーライドして実装する必要があります
        
        Returns:
            list: マンガデータのリスト。各要素は次のキーを含む辞書:
                - title (str): マンガタイトル
                - author (str): 著者名
                - first_book_title (str, optional): 第1巻タイトル
                - free_chapters (int): 無料話数
                - free_books (int): 無料冊数
                - category_id (str): カテゴリID (省略可、デフォルトは 'all')
                - rank (int): ランキング順位
                
            注意: 'manga'キーを含む場合は後方互換性のため既存のMangaオブジェクトを使用します
        """
        raise NotImplementedError("このメソッドは子クラスで実装する必要があります")