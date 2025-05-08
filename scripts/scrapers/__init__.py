"""
スクレイパーモジュールの初期化
各ストア用のスクレイパーを登録します
"""
import logging
from scripts.scrapers.registry import ScraperRegistry
from scripts.scrapers.ebookstore_a import MangaOukokuScraper
from scripts.scrapers.ebookstore_b import EbookStoreBScraper

logger = logging.getLogger(__name__)

def register_scrapers():
    """
    スクレイパーをレジストリに登録します
    
    新しい電子書籍ストアを追加する場合は、ここに登録してください
    """
    # ストアIDとスクレイパークラスのマッピング
    # ストアIDは実際のEbookStoreモデルのIDと一致させる必要があります
    scrapers = {
        1: MangaOukokuScraper,  # ストアID 1 = まんが王国
        2: EbookStoreBScraper   # ストアID 2 = 電子書籍ストアB (存在する場合)
    }
    
    # スクレイパーをレジストリに登録
    for store_id, scraper_class in scrapers.items():
        ScraperRegistry.register(store_id, scraper_class)
    
    logger.info(f"{len(scrapers)}個のスクレイパーを登録しました")

# モジュール初期化時にスクレイパーを登録
register_scrapers()