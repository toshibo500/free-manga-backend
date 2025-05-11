"""
スキマ用のスクレイパー
URL: https://www.sukima.me/book/ranking/
"""
import logging
import random
import re
import json
import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin
from scripts.scrapers.base import BaseStoreScraper
from scripts.utils import get_or_create_manga
from manga.models import Category, ScrapedManga, EbookStoreCategoryUrl

logger = logging.getLogger(__name__)

class EbookStoreBScraper(BaseStoreScraper):
    """
    スキマ用のスクレイパー
    
    スキマのランキングページからマンガデータをスクレイピングします
    各マンガの詳細ページにアクセスして著者情報を取得します
    """
    
    # ユーザーエージェントの設定
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    # 無料表記のパターン
    FREE_PATTERNS = [
        (r'(\d+)-(\d+)話無料', lambda m: int(m.group(2)) - int(m.group(1)) + 1),  # "1-52話無料" の形式
        (r'全巻無料\((\d+)話\)', lambda m: int(m.group(1))),  # "全巻無料(19話)" の形式
        (r'全巻([\d,]+)話無料', lambda m: int(m.group(1).replace(',', ''))),  # "全巻12,345話無料" の形式
        (r'(\d+)話まで無料', lambda m: int(m.group(1))),  # "10話まで無料" の形式
        (r'(\d+)話分無料', lambda m: int(m.group(1))),  # "10話分無料" の形式
        (r'第(\d+)話まで無料', lambda m: int(m.group(1))),  # "第10話まで無料" の形式
        (r'(\d+)話.*無料', lambda m: int(m.group(1))),  # "10話無料" の形式
        (r'無料(\d+)話', lambda m: int(m.group(1))),  # "無料10話" の形式
        (r'(\d+)話', lambda m: int(m.group(1))),  # 単純な "10話" の形式
    ]
    
    def _scrape(self):
        """
        スキマからランキングデータをスクレイピングします
        
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
                # スキマサイトの構造に合わせて適切なセレクタを使用
                ranking_items = soup.select('div.row.grid_item > div')
                if not ranking_items:
                    # 他の可能性のあるセレクタを試す
                    selectors = ['div.ranking-item', 'div.comic-item', '.comic-card', '.ranking-list > div']
                    for selector in selectors:
                        ranking_items = soup.select(selector)
                        if ranking_items:
                            logger.info(f"代替セレクタ '{selector}' で {len(ranking_items)} 件のランキングアイテムが見つかりました")
                            break
                
                logger.info(f"{len(ranking_items)} 件のランキングアイテムが見つかりました")
                
                # ランキングアイテムを処理（テストモードではtest_item_limit件、通常モードでは100件まで）
                items_to_process = min(test_item_limit if test_mode else 100, len(ranking_items))
                logger.info(f"処理対象: {items_to_process}件のランキングアイテム")
                
                for i, item in enumerate(ranking_items[:items_to_process]):
                    try:
                        # 順位の取得
                        rank_elem = item.select_one('div.ranking-label')
                        rank = int(rank_elem.text.strip()) if rank_elem else (i + 1)
                        
                        # タイトルの取得
                        title = self._extract_title(item)
                        if not title:
                            logger.warning(f"タイトルが見つかりません (rank: {rank})")
                            continue
                        
                        # 詳細ページURLの取得
                        detail_url = self._extract_detail_url(item)
                        
                        # 著者の取得 (詳細ページから)
                        author = "不明"
                        if detail_url:
                            author = self._fetch_author_from_detail_page(detail_url)
                        
                        # 詳細ページから著者が取得できなかった場合、一覧ページから取得を試みる
                        if not author or author == "不明":
                            author = self._extract_author(item)
                        
                        # 無料話数を取得
                        free_chapters = self._extract_free_chapters(item)
                        
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
                                        'free_books': 0,  # スキマでは冊数の概念がないため0を設定
                                        'rank': rank
                                    }
                                )
                            except Exception as e:
                                logger.warning(f"ScrapedManga重複エラー回避: {e}")
                                
                        # マンガデータリストに追加
                        manga_data.append({
                            'manga': manga,
                            'free_chapters': free_chapters,
                            'free_books': 0,  # スキマでは冊数の概念がないため0を設定
                            'category_id': cat_url.category.id,
                            'rank': rank
                        })
                        
                        # 進捗ログ（10アイテムごと）
                        if (i + 1) % 10 == 0:
                            logger.info(f"処理進捗: {i + 1}/{min(len(ranking_items), 100)} アイテム完了")
                        
                        # 次のリクエスト前に短い待機時間を入れる（サーバー負荷軽減）
                        time.sleep(random.uniform(0.5, 3.0))
                        
                    except Exception as e:
                        logger.warning(f"マンガアイテムの解析中にエラーが発生しました (rank: {i+1}): {e}")
            
            except Exception as e:
                logger.error(f"カテゴリ {cat_url.category.name} のスクレイピング中にエラー: {e}")
                
        self._report_stats(manga_data)
        return manga_data

    def _extract_title(self, item):
        """
        アイテムからタイトルを抽出
        
        Args:
            item: BeautifulSoup要素
            
        Returns:
            str: タイトル
        """
        # まずはスキマの標準的なタイトル要素を探す
        title_elem = item.select_one('div.title-name-content div')
        if title_elem and title_elem.text.strip():
            return title_elem.text.strip()
            
        # 他の可能性のあるセレクタを試す
        selectors = [
            '.title', '.book-title', 'h2', 'h3', 'h4', '.name',
            '.manga-title', 'a[href*="comic"]', '.comic-title'
        ]
        
        for selector in selectors:
            elem = item.select_one(selector)
            if elem and elem.text.strip():
                return elem.text.strip()
                
        # 明示的なタイトル要素が見つからない場合は、テキストノードから探す
        text_nodes = [text for text in item.stripped_strings]
        for text in text_nodes:
            # 長めのテキストで、作者表記や無料表記を含まないものがタイトルの可能性が高い
            if len(text) > 5 and '作' not in text and '著' not in text and '無料' not in text:
                return text.strip()
                
        return "不明"
        
    def _extract_author(self, item):
        """
        アイテムから著者を抽出
        
        Args:
            item: BeautifulSoup要素
            
        Returns:
            str: 著者名
        """
        # スキマの著者情報を含む要素を探す
        author_selectors = [
            '.author', '.writer', '.creator', '.artist',
            '.book-author', '.manga-author', '.author-name'
        ]
        
        for selector in author_selectors:
            elem = item.select_one(selector)
            if elem and elem.text.strip():
                return self._clean_author_name(elem.text.strip())
                
        # テキストノードから著者情報を探す
        for text in item.stripped_strings:
            if '作' in text or '著' in text:
                author = text.strip()
                if ":" in author or "：" in author:
                    author = author.split(":", 1)[1].strip()
                return self._clean_author_name(author)
                
        return "不明"
        
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
            
        # 余計な接頭辞や接尾辞を削除
        prefixes = ['著者:', '著者：', '作:', '作：', '著:', '原作:', '原作：', '漫画:', '漫画：', 
                    '作者:', '作者：', '著者 ', '作者 ', 'Author:', 'Writer:']
        for prefix in prefixes:
            if author.startswith(prefix):
                author = author[len(prefix):].strip()
                
        # その他のクリーンアップ処理
        author = re.sub(r'[\(\（].*?[\)\）]', '', author)  # 括弧内の情報を削除
        author = re.sub(r'作|著|漫画|原作|マンガ|著者|作者|先生|\s*[:：]\s*', '', author)  # 余計な文字を削除
        
        # HTMLタグが残っている場合は除去
        author = re.sub(r'<[^>]+>', '', author)
        
        # 空白文字を整理
        author = re.sub(r'\s+', ' ', author).strip()
        
        # リンクなどの余計な情報を削除
        if 'http' in author or '/' in author:
            parts = re.split(r'https?://|www\.|/|\s+', author)
            clean_parts = [p for p in parts if p and len(p) > 1 and '.' not in p]
            if clean_parts:
                author = clean_parts[0]
            else:
                return "不明"
        
        # 長すぎる場合はカット (おそらく著者名ではなく説明文などを誤って取得した場合)
        if len(author) > 50:
            return "不明"
        
        # 最終チェック - 著者名らしい文字列になっているか
        if not author or author == "," or len(author) < 2:
            return "不明"
            
        # 先頭と末尾の余分な文字を削除
        author = author.strip('.,、。 　:;-–—')
        
        return author if author else "不明"
        
    def _extract_free_chapters(self, item):
        """
        無料話数情報を抽出
        
        Args:
            item: BeautifulSoup要素
            
        Returns:
            int: 無料話数
        """
        free_chapters = 0
        
        # スキマの標準的な無料表示要素を探す
        free_elem = item.select_one('div.bg-free')
        if free_elem:
            free_text = free_elem.text.strip()
            # 複数のパターンを試す
            for pattern, extractor in self.FREE_PATTERNS:
                match = re.search(pattern, free_text)
                if match:
                    try:
                        free_chapters = extractor(match)
                        break
                    except (ValueError, IndexError) as e:
                        logger.warning(f"無料話数の解析エラー: {e}")
        
        # 他の可能性のある要素も確認
        if free_chapters == 0:
            free_selectors = ['.free', '.free-label', '.free-chapter', '.free-content']
            for selector in free_selectors:
                elem = item.select_one(selector)
                if elem:
                    # 全テキストノードに対して無料話数パターンを試す
                    for text in elem.stripped_strings:
                        for pattern, extractor in self.FREE_PATTERNS:
                            match = re.search(pattern, text)
                            if match:
                                try:
                                    free_chapters = extractor(match)
                                    break
                                except (ValueError, IndexError) as e:
                                    logger.warning(f"無料話数の解析エラー: {e}")
                        if free_chapters > 0:
                            break
        
        # ページ内の全てのテキストを対象に無料話数を探す
        if free_chapters == 0:
            for text in item.stripped_strings:
                if '無料' in text:
                    for pattern, extractor in self.FREE_PATTERNS:
                        match = re.search(pattern, text)
                        if match:
                            try:
                                free_chapters = extractor(match)
                                break
                            except (ValueError, IndexError) as e:
                                logger.warning(f"無料話数の解析エラー: {e}")
                    if free_chapters > 0:
                        break
                        
        return free_chapters
        
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
            # 詳細ページは通常より長めに待機（サーバー負荷対策）
            if '/book/title/' in url:
                time.sleep(random.uniform(2.0, 4.0))
            else:
                time.sleep(random.uniform(1.0, 3.0))
            
            # カスタムヘッダーでよりブラウザっぽくする
            custom_headers = self.HEADERS.copy()
            custom_headers['Referer'] = 'https://www.sukima.me/book/ranking/'
            custom_headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            
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

    def _extract_detail_url(self, item):
        """
        アイテムからマンガ詳細ページのURLを抽出
        
        Args:
            item: BeautifulSoup要素
            
        Returns:
            str: 詳細ページの完全なURL（取得できない場合はNone）
        """
        base_url = "https://www.sukima.me"
        
        # メインのアンカータグを探す
        main_link = item.select_one('a[href*="/book/title/"]')
        if main_link and main_link.get('href'):
            # 相対URLを絶対URLに変換
            relative_url = main_link.get('href')
            abs_url = urljoin(base_url, relative_url)
            logger.debug(f"詳細URL検出: {abs_url}")
            return abs_url
            
        # 他の可能性のあるセレクタを試す
        selectors = [
            'a[href*="comic"]', 'a[href*="book"]', 'a[href*="manga"]',
            'a.title-link', '.title a', '.book-title a'
        ]
        
        for selector in selectors:
            link = item.select_one(selector)
            if link and link.get('href'):
                relative_url = link.get('href')
                if relative_url and not relative_url.startswith(('http://', 'https://')):
                    abs_url = urljoin(base_url, relative_url)
                    logger.debug(f"代替セレクタ '{selector}' で詳細URL検出: {abs_url}")
                    return abs_url
                elif relative_url:
                    logger.debug(f"代替セレクタ '{selector}' で絶対URL検出: {relative_url}")
                    return relative_url
                
        logger.warning("詳細ページのURLが見つかりませんでした")
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
            
            # スキマの標準的な著者リンクを検索 (class="author"があるaタグから最初の一つだけ取得)
            author_link = soup.select_one('a.author')
            if author_link and author_link.text.strip():
                author = author_link.text.strip()
                logger.info(f"詳細ページから著者情報を取得: {author}")
                return self._clean_author_name(author)
            
            # 著者情報が見つからない場合
            logger.warning(f"詳細ページから著者情報を取得できませんでした: {detail_url}")
            return "不明"
            
        except Exception as e:
            logger.error(f"詳細ページからの著者情報取得中にエラーが発生: {e}")
            return "不明"

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
        
        # 著者と無料話数の統計
        authors_found = sum(1 for m in manga_data if m['manga'].author != "不明")
        free_chapters_found = sum(1 for m in manga_data if m['free_chapters'] > 0)
        
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
        logger.info("-" * 30)
        logger.info("カテゴリ別集計:")
        for cat, count in category_counts.items():
            logger.info(f"- {cat}: {count}件")
        logger.info("=" * 50)