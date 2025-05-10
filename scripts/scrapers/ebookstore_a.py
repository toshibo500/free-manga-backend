"""
まんが王国用のスクレイパー
URL: https://comic.k-manga.jp/rank/
"""
import logging
import time
import re
import requests
from bs4 import BeautifulSoup
from scripts.scrapers.base import BaseStoreScraper
from scripts.utils import get_or_create_manga
from manga.models import Category, ScrapedManga, EbookStoreCategoryUrl

logger = logging.getLogger(__name__)

class MangaOukokuScraper(BaseStoreScraper):
    """
    まんが王国用のスクレイパー
    URL: https://comic.k-manga.jp/rank/
    """
    
    # ユーザーエージェントの設定（Webサイトによってはブロックされることがあるため）
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    def _scrape(self):
        """
        まんが王国からランキングデータをスクレイピングします
        
        Returns:
            list: マンガデータのリスト
        """
        logger.info(f"{self.store.name}の全カテゴリURLからデータのスクレイピングを開始します...")
        manga_data = []
        scraping_history = getattr(self, 'scraping_history', None)
        # ストアカテゴリURLごとに処理
        for cat_url in EbookStoreCategoryUrl.objects.filter(store=self.store):
            url = cat_url.url
            category_objs = [cat_url.category]
            logger.info(f"カテゴリ: {cat_url.category.name} / URL: {url} のスクレイピングを開始")
            try:
                response = self._fetch_page(url)
                if not response:
                    logger.error(f"ページを取得できませんでした: {url}")
                    continue
                soup = BeautifulSoup(response, 'html.parser')
                
                rank = 1
                potential_selectors = [
                    '.rank-item', '.ranking-item', '.item', '.list-item', 
                    '.comic-item', '.manga-list-item', '.title-item',
                    'ul.rank-list > li', '.rank-list .item', '.ranking .item',
                    '.book-list > li', '.content-list > li'
                ]
                
                manga_items = []
                for selector in potential_selectors:
                    items = soup.select(selector)
                    if items:
                        logger.info(f"セレクタ '{selector}' で {len(items)} 件のアイテムが見つかりました")
                        manga_items = items
                        break
                
                if not manga_items:
                    logger.info("ランキングアイテムが見つかりませんでした。タイトル要素を探します...")
                    title_elements = soup.find_all(['h2', 'h3', 'h4', '.title', '.book-title'])
                    if title_elements:
                        logger.info(f"{len(title_elements)} 件のタイトル要素が見つかりました")
                        for i, title_elem in enumerate(title_elements[:100]):
                            try:
                                title = title_elem.text.strip()
                                if not title:
                                    logger.warning(f"空タイトルをスキップ (rank: {i+1})")
                                    continue
                                author = "不明"
                                author_elem = None
                                next_elems = list(title_elem.next_siblings)
                                for elem in next_elems:
                                    if elem.name and elem.text and ("作" in elem.text or "著" in elem.text):
                                        author_elem = elem
                                        break
                                if not author_elem and title_elem.parent:
                                    for elem in title_elem.parent.find_all(text=True):
                                        if "作" in elem or "著" in elem:
                                            author = elem.strip()
                                            if ":" in author or "：" in author:
                                                author = author.split(":", 1)[1].strip()
                                            break
                                if author_elem:
                                    author = author_elem.text.strip()
                                author = self._clean_author_name(author)
                                # 空文字やNoneのタイトル・著者はスキップ
                                if not title or not author or title == "不明" or author == "不明":
                                    logger.warning(f"空または不明なタイトル/著者をスキップ: title='{title}', author='{author}' (rank: {i+1})")
                                    continue
                                # 追加のバリデーション: title/authorが空文字やNone、または空白のみの場合もスキップ
                                if not isinstance(title, str) or not isinstance(author, str) or not title.strip() or not author.strip():
                                    logger.warning(f"空または無効なタイトル/著者をスキップ: title='{title}', author='{author}' (rank: {i+1})")
                                    continue
                                manga, _ = get_or_create_manga(
                                    title=title.strip(),
                                    author=author.strip(),
                                    categories=category_objs
                                )
                                if scraping_history is not None:
                                    try:
                                        ScrapedManga.objects.update_or_create(
                                            scraping_history=scraping_history,
                                            manga=manga,
                                            defaults={
                                                'free_chapters': 0,
                                                'free_books': 0,
                                                'rank': i + 1
                                            }
                                        )
                                    except Exception as e:
                                        logger.warning(f"ScrapedManga重複エラー回避: {e}")
                                manga_data.append({
                                    'title': title,
                                    'author': author,
                                    'free_chapters': 0,
                                    'free_books': 0,
                                    'category_id': cat_url.category.id,
                                    'rank': i + 1
                                })
                            except Exception as e:
                                logger.warning(f"アイテム解析中にエラーが発生しました (rank: {i+1}): {e}")
                else:
                    for i, item in enumerate(manga_items[:100]):
                        try:
                            title = "不明"
                            for title_selector in ['.title', '.book-title', 'h2', 'h3', 'h4', 'a', '.name']:
                                title_elem = item.select_one(title_selector)
                                if title_elem and title_elem.text.strip():
                                    title = title_elem.text.strip()
                                    break
                            if title == "不明":
                                for text in item.stripped_strings:
                                    if len(text) > 5 and "作" not in text and "著" not in text:
                                        title = text
                                        break
                            author = "不明"
                            author_elem = item.select_one('.book-list--author')
                            if author_elem:
                                author_spans = author_elem.select('.book-list--author-item')
                                if author_spans:
                                    authors = [span.text.strip() for span in author_spans if span.text.strip()]
                                    author = '・'.join(authors)
                                    suffix = author_elem.text.strip()
                                    if suffix.endswith('他') or suffix.endswith('ほか'):
                                        if not author.endswith('他') and not author.endswith('ほか'):
                                            author += ' 他'
                                else:
                                    author = author_elem.text.strip()
                            if author == "不明":
                                for author_selector in ['.author', '.writer', '.creator', '.artist']:
                                    author_elem = item.select_one(author_selector)
                                    if author_elem and author_elem.text.strip():
                                        author = author_elem.text.strip()
                                        break
                                if author == "不明":
                                    for text in item.stripped_strings:
                                        if "作" in text or "著" in text:
                                            author = text.strip()
                                            if ":" in author or "：" in author:
                                                author = author.split(":", 1)[1].strip()
                                            break
                            author = self._clean_author_name(author)
                            # 空文字やNoneのタイトル・著者はスキップ
                            if not title or not author or title == "不明" or author == "不明":
                                logger.warning(f"空または不明なタイトル/著者をスキップ: title='{title}', author='{author}' (rank: {i+1})")
                                continue
                            # 追加のバリデーション: title/authorが空文字やNone、または空白のみの場合もスキップ
                            if not isinstance(title, str) or not isinstance(author, str) or not title.strip() or not author.strip():
                                logger.warning(f"空または無効なタイトル/著者をスキップ: title='{title}', author='{author}' (rank: {i+1})")
                                continue
                            free_chapters = 0
                            free_books = 0
                            free_book_elem = item.select_one('aside.icon-text.icon-text__jikkuri')
                            if free_book_elem and '冊無料' in free_book_elem.text:
                                books_match = re.search(r'(\d+)冊無料', free_book_elem.text)
                                if books_match:
                                    free_books = int(books_match.group(1))
                                    logger.info(f"無料冊数を検出: {free_books}冊 (rank: {i+1})")
                            for text in item.stripped_strings:
                                chapters_match = re.search(r'(\d+)話無料', text)
                                if chapters_match:
                                    free_chapters = int(chapters_match.group(1))
                                if free_books == 0 and '冊無料' in text:
                                    books_match = re.search(r'(\d+)冊無料', text)
                                    if books_match:
                                        free_books = int(books_match.group(1))
                            if free_books == 0:
                                for book_selector in ['.free-volumes', '.volume-free', '.free-book']:
                                    book_elem = item.select_one(book_selector)
                                    if book_elem and '冊' in book_elem.text:
                                        books_match = re.search(r'(\d+)冊', book_elem.text)
                                        if books_match:
                                            free_books = int(books_match.group(1))
                                            break
                            manga, _ = get_or_create_manga(
                                title=title,
                                author=author,
                                categories=category_objs
                            )
                            if scraping_history is not None:
                                try:
                                    ScrapedManga.objects.update_or_create(
                                        scraping_history=scraping_history,
                                        manga=manga,
                                        defaults={
                                            'free_chapters': free_chapters,
                                            'free_books': free_books,
                                            'rank': i + 1
                                        }
                                    )
                                except Exception as e:
                                    logger.warning(f"ScrapedManga重複エラー回避: {e}")
                            manga_data.append({
                                'manga': manga,
                                'free_chapters': free_chapters,
                                'free_books': free_books,
                                'category_id': cat_url.category.id,
                                'rank': i + 1
                            })
                        except Exception as e:
                            logger.warning(f"マンガアイテムの解析中にエラーが発生しました (rank: {i+1}): {e}")
            except Exception as e:
                logger.error(f"カテゴリ {cat_url.category.name} のスクレイピング中にエラー: {e}")
        return manga_data
    
    def _clean_author_name(self, author_text):
        """
        著者名から不要なテキスト（あらすじなど）を削除します
        
        Args:
            author_text (str): 抽出された著者テキスト
            
        Returns:
            str: クリーンアップされた著者名
        """
        # 著者名が見つからない場合
        if not author_text or author_text == "不明":
            return author_text
        
        # ケース1: 明確な著者区切り文字がある場合
        for separator in ["著：", "著:", "作：", "作:"]:
            if separator in author_text:
                parts = author_text.split(separator, 1)
                if len(parts) > 1:
                    author_text = parts[1].strip()
        
        # ケース2: 長すぎる文章はあらすじの可能性が高い（句読点で判断）
        if len(author_text) > 50 or "。" in author_text:
            # 最初の句点までを取得
            parts = author_text.split("。", 1)
            if len(parts) > 1:
                # 句点の前の部分が短い場合は著者名として扱う
                if len(parts[0]) < 30:
                    author_text = parts[0].strip()
                else:
                    # 長すぎる場合は著者名不明とする
                    return "不明"
        
        # 改行や余分なスペースを削除
        author_text = author_text.replace("\n", " ").replace("\r", " ")
        while "  " in author_text:  # 連続する空白を1つにまとめる
            author_text = author_text.replace("  ", " ")
        
        return author_text.strip()
    
    def _fetch_page(self, url):
        """
        指定されたURLのページを取得します
        
        Args:
            url (str): 取得するページのURL
            
        Returns:
            str: HTML内容
        """
        try:
            logger.info(f"ページを取得: {url}")
            response = requests.get(url, headers=self.HEADERS, timeout=30)
            
            # HTTPステータスコードのチェック
            if response.status_code != 200:
                logger.error(f"HTTPエラー: {response.status_code}")
                return None
                
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"ページ取得中にエラーが発生しました: {e}")
            return None