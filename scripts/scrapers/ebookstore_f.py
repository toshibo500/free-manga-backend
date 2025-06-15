"""
ブックライブ用のスクレイパー
ストアID: 6
Vue.jsでレンダリングされるページに対応
"""
import logging
import random
import re
import time
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from scripts.scrapers.base import BaseStoreScraper
from manga.models import Category, EbookStoreCategoryUrl

logger = logging.getLogger(__name__)

class EbookStoreFScraper(BaseStoreScraper):
    """
    ブックライブ用のスクレイパー
    
    ブックライブのランキングページからマンガデータをスクレイピングします
    """
    
    STORE_ID = 6
    
    # ユーザーエージェントの設定
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    def __init__(self, store_id):
        """
        初期化時にWebDriverを設定
        """
        super().__init__(store_id)
        self.driver = None
        
    def _setup_driver(self):
        """
        Seleniumのウェブドライバーを設定します
        """
        if self.driver is not None:
            return self.driver
            
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # ヘッドレスモード
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36')
        
        # Chromiumのバイナリパスを設定（Dockerコンテナ内）
        chrome_options.binary_location = '/usr/bin/chromium'
        
        try:
            # ChromeDriverのサービスを設定
            service = Service('/usr/bin/chromedriver')
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(10)
            logger.info("Seleniumドライバーの初期化が完了しました")
            return self.driver
        except Exception as e:
            logger.error(f"Seleniumドライバーの初期化に失敗しました: {e}")
            raise
    
    def _cleanup_driver(self):
        """
        ウェブドライバーを終了します
        """
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                logger.info("Seleniumドライバーを終了しました")
            except Exception as e:
                logger.warning(f"Seleniumドライバーの終了中にエラー: {e}")

    def _fetch_page_with_selenium(self, url, max_wait_time=30):
        """
        SeleniumでVue.jsページを取得し、レンダリング完了まで待機します
        
        Args:
            url (str): 取得するページのURL
            max_wait_time (int): 最大待機時間（秒）
            
        Returns:
            str: レンダリング完了後のHTML内容
        """
        try:
            logger.info(f"Seleniumでページを取得: {url}")
            
            # ページにアクセス
            self.driver.get(url)
            
            # Vue.jsのレンダリング完了を待機
            # ランキングリストが表示されるまで待機
            try:
                WebDriverWait(self.driver, max_wait_time).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'ul[data-media="pc"].p-book-list'))
                )
                logger.info("Vue.jsのレンダリングが完了しました")
                
                # 追加の待機時間でコンテンツの完全読み込みを確保
                time.sleep(2)
                
            except TimeoutException:
                logger.warning(f"ランキングリストの読み込みがタイムアウトしました: {url}")
                # タイムアウトしても一応HTMLを取得してみる
            
            # レンダリング後のHTMLを取得
            html_content = self.driver.page_source
            logger.info(f"HTML内容を取得しました（長さ: {len(html_content)}文字）")
            
            return html_content
            
        except Exception as e:
            logger.error(f"Seleniumでのページ取得中にエラーが発生しました: {e}")
            return None

    def _scrape(self):
        """
        ブックライブからランキングデータをスクレイピングします
        
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
        
        # Seleniumドライバーを初期化
        try:
            self._setup_driver()
            
            # ストアカテゴリURLごとに処理
            for cat_url in EbookStoreCategoryUrl.objects.filter(store=self.store):
                url = cat_url.url
                category_objs = [cat_url.category]
                logger.info(f"カテゴリ: {cat_url.category.name} / URL: {url} のスクレイピングを開始")
                
                try:
                    # Seleniumでページを取得
                    html_content = self._fetch_page_with_selenium(url)
                    if not html_content:
                        logger.error(f"ページを取得できませんでした: {url}")
                        continue
                    
                    soup = BeautifulSoup(html_content, 'html.parser')

                    # <div id="index_vue" class="" data-v-app="">の内容をログ出力（デバッグ用）
                    # index_vue_div = soup.find('div', id='index_vue')
                    # if index_vue_div:
                    #     logger.info(f"index_vue_divの内容: {index_vue_div.prettify()}")
                    # else:
                    #     logger.warning(f"index_vue_divが見つかりません: {url}")

                    # ランキングリストを取得
                    ranking_list = soup.select('ul.p-book-list')
                    if not ranking_list:
                        logger.warning(f"ランキングリストが見つかりません: {url}")
                        continue
                    
                    # 各マンガアイテムを取得
                    manga_items = ranking_list[0].select('li')
                    logger.info(f"{len(manga_items)} 件のランキングアイテムが見つかりました")
                    
                    # ランキングアイテムを処理（テストモードではtest_item_limit件、通常モードでは100件まで）
                    items_to_process = min(test_item_limit if test_mode else 100, len(manga_items))
                    logger.info(f"処理対象: {items_to_process}件のランキングアイテム")
                    
                    for i, item in enumerate(manga_items[:items_to_process]):
                        try:
                            # 順位は配列のインデックス + 1
                            rank = i + 1
                            
                            # 第1巻タイトルの取得
                            title_elem = item.select_one('p[data-media="pc"].p-no-charge-book-item__title a')
                            if not title_elem:
                                logger.warning(f"第1巻タイトルが見つかりません (rank: {rank})")
                                continue
                                
                            first_book_title = title_elem.text.strip()
                            
                            if not first_book_title:
                                logger.warning(f"第1巻タイトルが空です (rank: {rank})")
                                continue
                            
                            # タイトルの生成（第1巻タイトルから巻数を除去）
                            title = self._extract_title_from_first_book(first_book_title)
                            
                            # 著者の取得
                            author_elem = item.select_one('div[data-media="pc"].p-no-charge-book-item__author-name')
                            author = "不明"
                            if author_elem:
                                author = author_elem.text.strip()
                                author = self._clean_author_name(author)
                            
                            # 無料冊数の取得
                            free_books = 0
                            free_books_elem = item.select_one('span.p-no-charge-book-item__tag__no-charge-category-count')
                            if free_books_elem:
                                free_books_text = free_books_elem.text.strip()
                                free_books_match = re.search(r'(\d+)', free_books_text)
                                if free_books_match:
                                    free_books = int(free_books_match.group(1))
                            
                            # 無料話数は常に0
                            free_chapters = 0
                            
                            # 空白やNoneのタイトル・著者はスキップ
                            if not title or not author or title == "不明" or author == "不明":
                                logger.warning(f"無効なタイトルまたは著者をスキップ: '{title}' / '{author}' (rank: {rank})")
                                continue

                            # 注: Mangaオブジェクトの作成はBaseStoreScraper._save_data()で行われます
                                    
                            # マンガデータリストに追加
                            manga_data.append({
                                'title': title,
                                'author': author,
                                'first_book_title': first_book_title,
                                'free_chapters': free_chapters,
                                'free_books': free_books,
                                'category_id': cat_url.category.id,
                                'rank': rank
                            })
                            
                            logger.info(f"抽出完了: rank={rank}, title={title}, author={author}, "
                                      f"free_chapters={free_chapters}, free_books={free_books}, "
                                      f"first_book_title={first_book_title}")
                            
                            # 進捗ログ（10アイテムごと）
                            if (i + 1) % 10 == 0:
                                logger.info(f"処理進捗: {i + 1}/{min(len(manga_items), items_to_process)} アイテム完了")
                            
                            # 次のリクエスト前に短い待機時間を入れる（サーバー負荷軽減）
                            time.sleep(random.uniform(0.5, 2.0))
                            
                        except Exception as e:
                            logger.warning(f"マンガアイテムの解析中にエラーが発生しました (rank: {i+1}): {e}")
                    
                except Exception as e:
                    logger.error(f"カテゴリ {cat_url.category.name} のスクレイピング中にエラー: {e}")
                    
        finally:
            # ドライバーのクリーンアップ
            self._cleanup_driver()
                    
        self._report_stats(manga_data)
        return manga_data
    
    def _extract_title_from_first_book(self, first_book_title):
        """
        第1巻タイトルから巻数を除去してタイトルを抽出します
        
        Args:
            first_book_title (str): 第1巻タイトル
            
        Returns:
            str: 巻数を除去したタイトル
        """
        if not first_book_title:
            return "不明"
        
        # 巻数の除去パターン（優先度順に配置）
        volume_patterns = [
            # 括弧内の数字パターン（半角・全角両方）
            r'\s*\(1\)$',                # " (1)" または "(1)"
            r'\s*（1）$',                # " （1）" または "（1）"
            r'\s*\(１\)$',               # " (１)" または "(１)"
            r'\s*（１）$',               # " （１）" または "（１）"
            
            # 特別版と括弧の組み合わせ
            r'【特別版】\s*\(1\)$',      # "【特別版】 (1)" または "【特別版】(1)"
            r'【特別版】\s*（1）$',      # "【特別版】 （1）" または "【特別版】（1）"
            
            # 数字が直接続くパターン
            r'1$',                       # "1" (末尾の1)
            r'１$',                      # "１" (末尾の全角1)
            
            # スペース区切りの数字
            r'\s+1$',                    # " 1"
            r'\s+１$',                   # " １"
            r'　1$',                     # "　1"
            r'　１$',                    # "　１"
            
            # 巻数表記
            r'　１巻$',                  # "　１巻"
            r'\s+１巻$',                 # " １巻"
            r'\s+1巻$',                  # " 1巻"
            r'1巻$',                     # "1巻"
            r'１巻$',                    # "１巻"
            
            # 話数表記
            r'第1話$',                   # "第1話"
            r'第１話$',                  # "第１話"
            r'【第１話】$',              # "【第１話】"
            r'【第1話】$',               # "【第1話】"
            
            # 特典付き表記
            r'\s+1巻【特典付き】$',      # " 1巻【特典付き】"
            r'1巻【特典付き】$',         # "1巻【特典付き】"
        ]
        
        title = first_book_title
        for pattern in volume_patterns:
            original_title = title
            title = re.sub(pattern, '', title)
            # デバッグ用（必要に応じてコメントアウト）
            # if original_title != title:
            #     logger.debug(f"Pattern '{pattern}' matched: '{original_title}' -> '{title}'")
        
        return title.strip() if title.strip() else first_book_title

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
            
        # 著者名を整理
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
