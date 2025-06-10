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

    def _extract_manga_item(self, item, category_objs, scraping_history, cat_url):
        """
        1つのli.p-bookList_itemからマンガ情報を抽出し、登録する
        """
        import re
        # 順位
        rank_elem = item.select_one('span.p-book_leadItem.p-book_rank')
        rank = 0
        if rank_elem:
            m = re.search(r'(\d+)', rank_elem.text)
            if m:
                rank = int(m.group(1))
        # タイトル
        title_elem = item.select_one('dt.p-book_title a')
        title = title_elem.text.strip() if title_elem else "不明"
        # 著者
        author_elem = item.select_one('dd.p-book_author')
        author = author_elem.text.strip() if author_elem else "不明"
        # 無料話数
        free_chapters = 0
        free_elem = item.select_one('div.btn_free a')
        if free_elem:
            m = re.search(r'(\d+)話無料', free_elem.text)
            if m:
                free_chapters = int(m.group(1))
        # 無料冊数は常に0
        free_books = 0
        # マンガデータを作成・取得
        from scripts.utils import get_or_create_manga
        manga, _ = get_or_create_manga(
            title=title,
            author=author,
            categories=category_objs
        )
        if not manga:
            logger.warning(f"マンガの作成に失敗: {title} / {author}")
            return None
        # スクレイピング履歴がある場合、ScrapedMangaを作成
        if scraping_history is not None:
            from manga.models import ScrapedManga
            try:
                ScrapedManga.objects.update_or_create(
                    scraping_history=scraping_history,
                    manga=manga,
                    defaults={
                        'free_chapters': free_chapters,
                        'free_books': free_books,
                        'rank': rank
                    }
                )
            except Exception as e:
                logger.warning(f"ScrapedManga重複エラー回避: {e}")
        return {
            'manga': manga,
            'free_chapters': free_chapters,
            'free_books': free_books,
            'category_id': cat_url.category.id,
            'rank': rank
        }

    def _scrape(self):
        logger.info("めちゃコミランキングスクレイピング開始")
        manga_data = []
        scraping_history = getattr(self, 'scraping_history', None)
        test_mode = getattr(self, 'test_mode', False)
        test_item_limit = getattr(self, 'test_item_limit', 100) if test_mode else 100
        for cat_url in EbookStoreCategoryUrl.objects.filter(store_id=self.STORE_ID):
            base_url = cat_url.url
            logger.info(f"カテゴリ: {cat_url.category.name} - ベースURL: {base_url}")
            category_objs = [cat_url.category]
            item_count = 0
            for page in range(1, 6):  # 1ページ目から5ページ目まで
                page_url = f"{base_url}&page={page}"
                logger.info(f"フェッチ中: {page_url}")
                try:
                    response = requests.get(page_url, timeout=10)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "html.parser")
                    manga_items = soup.select('li.p-bookList_item')
                    logger.info(f"ページ{page}で{len(manga_items)}件のマンガデータを検出")
                    for i, item in enumerate(manga_items):
                        if test_mode and item_count >= test_item_limit:
                            break
                        result = self._extract_manga_item(item, category_objs, scraping_history, cat_url)
                        if result:
                            manga_data.append(result)
                            item_count += 1
                            if (item_count) % 10 == 0:
                                logger.info(f"進捗: {item_count}件 登録完了")
                    if test_mode and item_count >= test_item_limit:
                        break
                except Exception as e:
                    logger.warning(f"ページ取得失敗: {page_url} ({e})")
                time.sleep(1)  # サーバー負荷軽減のため1秒待機
        logger.info("めちゃコミランキングスクレイピング終了")
        self._report_stats(manga_data)
        return manga_data
