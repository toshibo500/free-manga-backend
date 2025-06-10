import time
import logging
import requests
from bs4 import BeautifulSoup
from manga.models import EbookStoreCategoryUrl
from scripts.scrapers.base import BaseStoreScraper

logger = logging.getLogger(__name__)

class EbookStoreEScraper(BaseStoreScraper):
    """
    めちゃコミ用のスクレイパー
    ストアID: 5
    各カテゴリごとに5ページ分ランキングページをフェッチします。
    """
    STORE_ID = 5

    def _scrape(self):
        logger.info("めちゃコミランキングスクレイピング開始")
        for cat_url in EbookStoreCategoryUrl.objects.filter(store_id=self.STORE_ID):
            base_url = cat_url.url
            logger.info(f"カテゴリ: {cat_url.category.name} - ベースURL: {base_url}")
            for page in range(1, 6):  # 1ページ目から5ページ目まで
                page_url = f"{base_url}&page={page}"
                logger.info(f"フェッチ中: {page_url}")
                try:
                    response = requests.get(page_url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "html.parser")
                    # ここでマンガデータの抽出処理を後で実装
                    logger.info(f"ページ{page}のHTMLを取得しました（カテゴリ: {cat_url.category.name}）")
                except Exception as e:
                    logger.warning(f"ページ取得失敗: {page_url} ({e})")
                time.sleep(1)  # サーバー負荷軽減のため1秒待機
        logger.info("めちゃコミランキングスクレイピング終了")
