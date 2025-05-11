"""
ebook japan用のスクレイパー
URL: https://www.ebookjapan.jp/ebj/ranking/
"""
import logging
import random
import re
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin
from scripts.scrapers.base import BaseStoreScraper
from scripts.utils import get_or_create_manga
from manga.models import Category, ScrapedManga, EbookStoreCategoryUrl

logger = logging.getLogger(__name__)

class EbookStoreCScraper(BaseStoreScraper):
    """
    ebook japan用のスクレイパー
    
    ebook japanのランキングページからマンガデータをスクレイピングします
    各マンガの詳細ページにアクセスして著者情報を取得します
    """
    
    # ユーザーエージェントの設定
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    def _scrape(self):
        """
        ebook japanからランキングデータをスクレイピングします
        
        Returns:
            list: マンガデータのリスト
        """
        logger.info(f"{self.store.name}の全カテゴリURLからデータのスクレイピングを開始します...")
        manga_data = []
        scraping_history = getattr(self, 'scraping_history', None)
        
        # テストモードかどうかチェック
        test_mode = getattr(self, 'test_mode', False)
        test_item_limit = getattr(self, 'test_item_limit', 100) if test_mode else 100
        
        if test_mode:
            logger.info(f"テストモードで実行中: 最大 {test_item_limit} アイテムのみ処理します")
        
        # ストアカテゴリURLごとに処理
        for cat_url in EbookStoreCategoryUrl.objects.filter(store=self.store):
            url = cat_url.url
            category_objs = [cat_url.category]
            logger.info(f"カテゴリ: {cat_url.category.name} / URL: {url} のスクレイピングを開始")
            
            try:
                # ページ取得と解析
                response = self._fetch_page(url)
                if not response:
                    logger.error(f"ページを取得できませんでした: {url}")
                    continue
                
                soup = BeautifulSoup(response, 'html.parser')
                
                # ランキングリストを取得
                ranking_items = soup.select('ul.grid-contents__list.contents-list li.contents-list__item.list-item')
                
                logger.info(f"{len(ranking_items)} 件のランキングアイテムが見つかりました")
                
                # ランキングアイテムを処理（テストモードではtest_item_limit件、通常モードでは100件まで）
                items_to_process = min(test_item_limit if test_mode else 100, len(ranking_items))
                logger.info(f"処理対象: {items_to_process}件のランキングアイテム")
                
                for i, item in enumerate(ranking_items[:items_to_process]):
                    try:
                        # 順位の取得（インデックス+1をランクとする）
                        rank = i + 1
                        
                        # タイトルの取得
                        title_elem = item.select_one('p.book-item__title.book-item__title--line-clamp')
                        title = title_elem.text.strip() if title_elem else "不明"
                        
                        if not title or title == "不明":
                            logger.warning(f"タイトルが見つかりません (rank: {rank})")
                            continue
                        
                        # 詳細ページURLの取得
                        detail_link = item.select_one('a.book-item.list-item__content')
                        if not detail_link or not detail_link.get('href'):
                            logger.warning(f"詳細ページリンクが見つかりません: {title} (rank: {rank})")
                            continue
                            
                        relative_url = detail_link.get('href')
                        detail_url = urljoin('https://www.ebookjapan.jp', relative_url)
                        
                        # 著者の取得 (詳細ページから)
                        author = self._fetch_author_from_detail_page(detail_url)
                        
                        # 無料冊数を取得
                        free_books = self._fetch_free_books_from_detail_page(detail_url)
                        
                        # 無料話数を取得
                        free_chapters = self._fetch_free_chapters_from_detail_page(detail_url)
                        
                        # 空白やNoneのタイトル・著者はスキップ
                        if not title or not author or title == "不明" or author == "不明":
                            logger.warning(f"無効なタイトルまたは著者をスキップ: '{title}' / '{author}' (rank: {rank})")
                            continue
                            
                        # マンガデータを作成・取得
                        manga, _ = get_or_create_manga(
                            title=title,
                            author=author,
                            categories=category_objs
                        )
                        
                        # マンガが作成できなかった場合はスキップ
                        if not manga:
                            logger.warning(f"マンガの作成に失敗しました: '{title}' (rank: {rank})")
                            continue
                            
                        # スクレイピング履歴がある場合、ScrapedMangaを作成
                        if scraping_history is not None:
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
                                
                        # マンガデータリストに追加
                        manga_data.append({
                            'manga': manga,
                            'free_chapters': free_chapters,
                            'free_books': free_books,
                            'category_id': cat_url.category.id,
                            'rank': rank
                        })
                        
                        # 進捗ログ（10アイテムごと）
                        if (i + 1) % 10 == 0:
                            logger.info(f"処理進捗: {i + 1}/{min(len(ranking_items), items_to_process)} アイテム完了")
                        
                        # 次のリクエスト前に短い待機時間を入れる（サーバー負荷軽減）
                        time.sleep(random.uniform(0.5, 5.0))
                        
                    except Exception as e:
                        logger.warning(f"マンガアイテムの解析中にエラーが発生しました (rank: {i+1}): {e}")
            
            except Exception as e:
                logger.error(f"カテゴリ {cat_url.category.name} のスクレイピング中にエラー: {e}")
                
        self._report_stats(manga_data)
        return manga_data

    def _fetch_page(self, url, retry_count=0, max_retries=3):
        """
        指定されたURLのページを取得します
        
        Args:
            url (str): 取得するページのURL
            retry_count (int): 現在の再試行回数
            max_retries (int): 最大再試行回数
            
        Returns:
            str: HTML内容
        """
        # 再試行回数が上限を超えた場合は処理を中止
        if retry_count > max_retries:
            logger.error(f"最大再試行回数({max_retries})を超えたため、処理を中止します: {url}")
            return None
        
        try:
            logger.info(f"ページを取得: {url} (試行回数: {retry_count + 1})")
            
            # ランダムな待機時間を入れてサーバーへの負荷を軽減
            time.sleep(random.uniform(1.0, 3.0))
            
            # カスタムヘッダーでよりブラウザっぽくする
            custom_headers = self.HEADERS.copy()
            custom_headers['Referer'] = 'https://www.ebookjapan.jp/ebj/ranking/'
            
            # リクエスト実行
            response = requests.get(url, headers=custom_headers, timeout=30)
            
            # HTTPステータスコードのチェック
            if response.status_code != 200:
                logger.warning(f"HTTPエラー: {response.status_code} - URL: {url}")
                
                # 429 (Too Many Requests) の場合は待機してリトライ
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.info(f"レート制限を検出。{retry_after}秒待機します。")
                    time.sleep(retry_after)
                    return self._fetch_page(url, retry_count + 1, max_retries)
                    
                # 5xx系サーバーエラーの場合は待機してリトライ
                elif 500 <= response.status_code < 600:
                    wait_time = (retry_count + 1) * 5  # 指数バックオフ
                    logger.info(f"サーバーエラー。{wait_time}秒後に再試行します。")
                    time.sleep(wait_time)
                    return self._fetch_page(url, retry_count + 1, max_retries)
                    
                # 他のエラーは一度だけ再試行
                elif retry_count < 1:
                    wait_time = random.uniform(3.0, 5.0)
                    logger.info(f"HTTPエラー後、{wait_time}秒待機してリトライします。")
                    time.sleep(wait_time)
                    return self._fetch_page(url, retry_count + 1, max_retries)
                    
                return None
                
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"ページ取得中にエラーが発生しました: {e}")
            
            # 接続エラー等の場合は一度だけ再試行
            if retry_count < 1:
                wait_time = random.uniform(5.0, 10.0)
                logger.info(f"接続エラー後、{wait_time}秒待機してリトライします。")
                time.sleep(wait_time)
                return self._fetch_page(url, retry_count + 1, max_retries)
                
            return None
            
    def _fetch_author_from_detail_page(self, detail_url):
        """
        マンガ詳細ページから著者情報を取得
        
        Args:
            detail_url (str): 詳細ページのURL
            
        Returns:
            str: 著者名（取得できない場合は"不明"）
        """
        try:
            # 詳細ページを取得
            logger.info(f"詳細ページから著者情報を取得: {detail_url}")
            response = self._fetch_page(detail_url)
            if not response:
                logger.warning(f"詳細ページを取得できませんでした: {detail_url}")
                return "不明"
                
            soup = BeautifulSoup(response, 'html.parser')
            
            # 著者情報を取得
            author_elem = soup.select_one('p.contents-detail__author')
            if author_elem and author_elem.select_one('a'):
                author = author_elem.select_one('a').text.strip()
                logger.info(f"詳細ページから著者情報を取得: {author}")
                return self._clean_author_name(author)
            
            # 著者情報が見つからない場合
            logger.warning(f"詳細ページから著者情報を取得できませんでした: {detail_url}")
            return "不明"
            
        except Exception as e:
            logger.error(f"詳細ページからの著者情報取得中にエラーが発生: {e}")
            return "不明"
            
    def _fetch_free_books_from_detail_page(self, detail_url):
        """
        マンガ詳細ページから無料冊数を取得
        
        Args:
            detail_url (str): 詳細ページのURL
            
        Returns:
            int: 無料冊数
        """
        try:
            # 詳細ページを取得
            logger.info(f"詳細ページから無料冊数を取得: {detail_url}")
            response = self._fetch_page(detail_url)
            if not response:
                logger.warning(f"詳細ページを取得できませんでした: {detail_url}")
                return 0
                
            soup = BeautifulSoup(response, 'html.parser')
            
            # 無料冊数を取得
            free_books = []
            free_items = soup.select('a.book-item.free-item__content')
            
            for item in free_items:
                title_elem = item.select_one('p.book-caption__title')
                if title_elem:
                    title_text = title_elem.text.strip()
                    # 巻数を抽出
                    volume_match = re.search(r'(\d+)', title_text)
                    if volume_match:
                        volume = int(volume_match.group(1))
                        free_books.append(volume)
                        
            # 最大の巻数を返す（無料冊数）
            if free_books:
                max_volume = max(free_books)
                logger.info(f"詳細ページから無料冊数を取得: {max_volume}冊")
                return max_volume
            
            # 無料タグがあるが巻数が取得できなかった場合は1とする
            if soup.select_one('span.tagtext.tagtext--carnation.tagtext--fill'):
                logger.info(f"詳細ページから無料タグを検出: 無料冊数を1とします")
                return 1
                
            logger.info(f"詳細ページから無料冊数を取得できませんでした: 0冊")
            return 0
            
        except Exception as e:
            logger.error(f"詳細ページからの無料冊数取得中にエラーが発生: {e}")
            return 0
            
    def _fetch_free_chapters_from_detail_page(self, detail_url):
        """
        マンガ詳細ページから無料話数を取得
        
        Args:
            detail_url (str): 詳細ページのURL
            
        Returns:
            int: 無料話数
        """
        try:
            # 詳細ページを取得
            logger.info(f"詳細ページから無料話数を取得: {detail_url}")
            response = self._fetch_page(detail_url)
            if not response:
                logger.warning(f"詳細ページを取得できませんでした: {detail_url}")
                return 0
                
            soup = BeautifulSoup(response, 'html.parser')
            
            # 連載アイテムを検索
            serial_item = soup.select_one('a.serial-story-item.free-item__content')
            if serial_item:
                # 無料話数タグを検索
                free_tag = serial_item.select_one('span.tagtext.tagtext--carnation.tagtext--fill.story-caption__tagtext')
                if free_tag:
                    # 無料話数を抽出
                    chapters_match = re.search(r'(\d+)話無料', free_tag.text)
                    if chapters_match:
                        free_chapters = int(chapters_match.group(1))
                        logger.info(f"詳細ページから無料話数を取得: {free_chapters}話")
                        return free_chapters
            
            logger.info(f"詳細ページから無料話数を取得できませんでした: 0話")
            return 0
            
        except Exception as e:
            logger.error(f"詳細ページからの無料話数取得中にエラーが発生: {e}")
            return 0

    def _clean_author_name(self, author):
        """
        著者名のクリーンアップ
        
        Args:
            author (str): クリーンアップ前の著者名
            
        Returns:
            str: クリーンアップ後の著者名
        """
        if not author:
            return "不明"
            
        # 原作：XXX　著：YYY の形式の場合は両方取得
        author = author.strip()
        
        # 空白文字を整理
        author = re.sub(r'\s+', ' ', author).strip()
        
        # 長すぎる場合はカット (おそらく著者名ではなく説明文などを誤って取得した場合)
        if len(author) > 50:
            return "不明"
        
        # 最終チェック - 著者名らしい文字列になっているか
        if not author or author == "," or len(author) < 2:
            return "不明"
            
        return author

    def _report_stats(self, manga_data):
        """
        スクレイピング結果の統計情報をログに出力
        
        Args:
            manga_data (list): 収集したマンガデータのリスト
        """
        if not manga_data:
            logger.warning("収集されたマンガデータがありません")
            return
            
        # 収集したデータの総数
        total_count = len(manga_data)
        
        # 著者と無料話数、無料冊数の統計
        authors_found = sum(1 for m in manga_data if m['manga'].author != "不明")
        free_chapters_found = sum(1 for m in manga_data if m['free_chapters'] > 0)
        free_books_found = sum(1 for m in manga_data if m['free_books'] > 0)
        
        # カテゴリごとの集計
        category_counts = {}
        for m in manga_data:
            cat_id = m['category_id']
            cat_name = Category.objects.get(id=cat_id).name
            if cat_name not in category_counts:
                category_counts[cat_name] = 0
            category_counts[cat_name] += 1
            
        # 結果をログ出力
        logger.info("=" * 50)
        logger.info("スクレイピング統計情報")
        logger.info("-" * 50)
        logger.info(f"総収集マンガ数: {total_count}")
        logger.info(f"著者情報あり: {authors_found}/{total_count} ({authors_found/total_count*100:.1f}%)")
        logger.info(f"無料話数あり: {free_chapters_found}/{total_count} ({free_chapters_found/total_count*100:.1f}%)")
        logger.info(f"無料冊数あり: {free_books_found}/{total_count} ({free_books_found/total_count*100:.1f}%)")
        logger.info("-" * 30)
        logger.info("カテゴリ別集計:")
        for cat, count in category_counts.items():
            logger.info(f"- {cat}: {count}件")
        logger.info("=" * 50)
