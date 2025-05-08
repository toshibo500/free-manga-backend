"""
スクレイパーレジストリ
各電子書籍ストア用のスクレイパーを登録・管理します
"""
import logging

logger = logging.getLogger(__name__)

class ScraperRegistry:
    """
    スクレイパー登録管理クラス
    各電子書籍ストアのスクレイパークラスを登録し、インスタンス化する機能を提供します
    """
    
    _registry = {}  # ストアID: スクレイパークラス のマッピング
    
    @classmethod
    def register(cls, store_id, scraper_class):
        """
        スクレイパークラスを登録します
        
        Args:
            store_id (int): 電子書籍ストアID
            scraper_class (class): スクレイパークラス（BaseStoreScraperのサブクラス）
        """
        cls._registry[store_id] = scraper_class
        logger.info(f"スクレイパー登録: ストアID {store_id}, クラス {scraper_class.__name__}")
    
    @classmethod
    def get_scraper(cls, store_id):
        """
        スクレイパーインスタンスを取得します
        
        Args:
            store_id (int): 電子書籍ストアID
        
        Returns:
            BaseStoreScraper: スクレイパーインスタンス
        
        Raises:
            ValueError: 指定されたstore_idに対応するスクレイパーがない場合
        """
        scraper_class = cls._registry.get(store_id)
        if not scraper_class:
            raise ValueError(f"ストアID {store_id} に対応するスクレイパーが登録されていません")
        
        return scraper_class(store_id)
    
    @classmethod
    def get_all_store_ids(cls):
        """
        登録されているすべての電子書籍ストアIDを取得します
        
        Returns:
            list: 電子書籍ストアIDのリスト
        """
        return list(cls._registry.keys())