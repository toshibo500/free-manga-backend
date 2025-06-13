"""
シーモア用のスクレイパー
URL: https://www.cmoa.jp/ranking/
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

class EbookStoreDScraper(BaseStoreScraper):
    """
    シーモア用のスクレイパー
    
    シーモアのランキングページからマンガデータをスクレイピングします
    各マンガの詳細ページにアクセスして著者情報を取得します
    """
    
    # ユーザーエージェントの設定
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    # ランキングページのパラメータ
    RANKING_PARAMS = "?page=1&order=up&disp_mode=easy"
    
    def _scrape(self):
        """
        シーモアからランキングデータをスクレイピングします
        
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
            if not url.endswith(self.RANKING_PARAMS):
                url = url + self.RANKING_PARAMS
                
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
                ranking_items = soup.select('ul#ranking_result_list li')
                
                logger.info(f"{len(ranking_items)} 件のランキングアイテムが見つかりました")
                
                # ランキングアイテムを処理（テストモードではtest_item_limit件、通常モードでは100件まで）
                items_to_process = min(test_item_limit if test_mode else 100, len(ranking_items))
                logger.info(f"処理対象: {items_to_process}件のランキングアイテム")
                
                for i, item in enumerate(ranking_items[:items_to_process]):
                    try:
                        # 順位の取得
                        rank_elem = item.select_one('div.rank_area')
                        if not rank_elem:
                            logger.warning(f"順位が見つかりません (index: {i})")
                            continue
                            
                        rank_text = rank_elem.text.strip()
                        rank_match = re.search(r'(\d+)', rank_text)
                        if not rank_match:
                            logger.warning(f"順位のパースに失敗しました: {rank_text}")
                            continue
                            
                        rank = int(rank_match.group(1))
                        
                        # タイトルの取得
                        title_elem = item.select_one('div.search_result_box_right a.title')
                        if not title_elem:
                            logger.warning(f"タイトルが見つかりません (rank: {rank})")
                            continue
                            
                        title = title_elem.text.strip()
                        
                        if not title:
                            logger.warning(f"タイトルが空です (rank: {rank})")
                            continue
                        
                        # 詳細ページURLの取得
                        detail_link = title_elem.get('href')
                        if not detail_link:
                            logger.warning(f"詳細ページリンクが見つかりません: {title} (rank: {rank})")
                            continue
                            
                        detail_url = urljoin('https://www.cmoa.jp', detail_link)

                        # 表示モードのパラメータをつける　?disp_mode=easy
                        if not detail_url.endswith('disp_mode=easy'):
                            detail_url += '?disp_mode=easy'
                        
                        # 詳細ページから著者情報、無料冊数、第1巻タイトルを一度に取得
                        author, free_books, first_book_title = self._fetch_details_from_page(detail_url)

                        # 無料話数は常に0
                        free_chapters = 0

                        # 空白やNoneのタイトル・著者はスキップ
                        if not title or not author or title == "不明" or author == "不明":
                            logger.warning(f"無効なタイトルまたは著者をスキップ: '{title}' / '{author}' (rank: {rank})")
                            continue

                        # マンガデータを作成・取得
                        manga, _ = get_or_create_manga(
                            title=title,
                            author=author,
                            categories=category_objs,
                            first_book_title=first_book_title  # Register first book title
                        )
                        
                        # マンガが作成できなかった場合はスキップ
                        if not manga:
                            logger.warning(f"マンガの作成に失敗しました: '{title}' (rank: {rank})")
                            continue
                            
                        # 注: BaseStoreScraper._save_data()がScrapedMangaを登録するため、ここでは登録しません
                                
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
            custom_headers['Referer'] = 'https://www.cmoa.jp/ranking/'
            
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
            
    def _fetch_details_from_page(self, detail_url):
        """
        マンガ詳細ページから著者情報、無料冊数、第1巻タイトルを一度に取得

        Args:
            detail_url (str): 詳細ページのURL

        Returns:
            tuple: (著者名, 無料冊数, 第1巻タイトル)
        """
        try:
            # 詳細ページを取得（1回のみ）
            logger.info(f"詳細ページからマンガ情報を取得: {detail_url}")
            response = self._fetch_page(detail_url)
            if not response:
                logger.warning(f"詳細ページを取得できませんでした: {detail_url}")
                return "不明", 0, None

            soup = BeautifulSoup(response, 'html.parser')

            # 著者情報を取得
            author = "不明"
            author_elem = soup.select_one('div.title_details_author_name')
            if author_elem:
                author = author_elem.text.strip()
                logger.info(f"詳細ページから著者情報を取得: {author}")
                author = self._clean_author_name(author)
            else:
                logger.warning(f"詳細ページから著者情報を取得できませんでした: {detail_url}")

            # 無料冊数を取得
            free_items = soup.select('ul.title_vol_easy_box li div.free_easy_m')
            free_books = len(free_items)
            logger.info(f"詳細ページから無料冊数を取得: {free_books}冊")

            # 第1巻タイトルを取得
            first_book_elem = soup.select_one('h1.titleName')
            first_book_title = first_book_elem.text.strip() if first_book_elem else None
            if first_book_title:
                logger.info(f"詳細ページから第1巻タイトルを取得: {first_book_title}")
            else:
                logger.warning(f"詳細ページから第1巻タイトルを取得できませんでした: {detail_url}")

            return author, free_books, first_book_title

        except Exception as e:
            logger.error(f"詳細ページからの情報取得中にエラーが発生: {e}")
            return "不明", 0, None

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
