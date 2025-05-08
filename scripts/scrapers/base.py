"""
基底スクレイパークラス
すべての電子書籍ストア用スクレイパーはこのクラスを継承します
"""
import logging
import traceback
from abc import ABC, abstractmethod
from datetime import datetime
from django.db import transaction
from manga.models import Category, ScrapingHistory, ScrapedManga, EbookStore

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
        # スクレイピング履歴を作成
        self.history = self._create_history()
        
        try:
            # スクレイピングを実行
            logger.info(f"{self.store.name} のスクレイピングを開始します")
            
            # コンテンツをスクレイピング
            manga_data_list = self._scrape()
            
            # データを保存
            self._save_data(manga_data_list)
            
            # 履歴を更新して成功を記録
            self._update_history_success()
            
            logger.info(f"{self.store.name} のスクレイピングが正常に完了しました")
            return True
        
        except Exception as e:
            # エラーを記録して失敗を記録
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
            manga_data_list (list): マンガデータのリスト
        """
        created_count = 0
        
        for i, manga_data in enumerate(manga_data_list):
            try:
                # 各データの保存を個別のトランザクションで実行
                with transaction.atomic():
                    # カテゴリを取得 (ない場合はデフォルトで 'all' を使用)
                    category_id = manga_data.get('category_id', 'all')
                    category = Category.objects.get(id=category_id)
                    
                    # 著者名が長すぎる場合は切り詰める
                    author = manga_data['author']
                    if len(author) > 250:  # 安全のため少し余裕を持たせる
                        author = author[:250] + '...'
                    
                    # データを保存
                    ScrapedManga.objects.create(
                        scraping_history=self.history,
                        title=manga_data['title'],
                        author=author,
                        free_chapters=manga_data['free_chapters'],
                        free_books=manga_data['free_books'],
                        category=category,
                        rank=manga_data['rank']
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
                - title (str): タイトル
                - author (str): 著者
                - free_chapters (int): 無料話数
                - free_books (int): 無料冊数
                - category_id (str): カテゴリID (省略可、デフォルトは 'all')
                - rank (int): ランキング順位
        """
        raise NotImplementedError("このメソッドは子クラスで実装する必要があります")