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
        logger.info(f"{self.store.name}からデータのスクレイピングを開始します...")
        
        url = self.store.url
        manga_data = []
        
        try:
            # ページを取得
            response = self._fetch_page(url)
            if not response:
                logger.error("ページを取得できませんでした")
                return []
            
            # HTML構造を詳細に分析してから処理を実行
            soup = BeautifulSoup(response, 'html.parser')
            
            # まずHTMLの基本構造を把握するためにデバッグ情報を出力
            logger.info(f"ページタイトル: {soup.title.text if soup.title else 'タイトルなし'}")
            
            # ランキングアイテムの検出
            # 実際のHTMLでは別のセレクタが使用されている可能性が高いため、より一般的なものを試す
            rank = 1
            
            # li.item または div.list-item など、ランキングアイテムの一般的なセレクタパターンを試す
            # 複数のパターンを試す
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
                # ランキングアイテムが見つからない場合、title要素を含む親要素を探す
                logger.info("ランキングアイテムが見つかりませんでした。タイトル要素を探します...")
                title_elements = soup.find_all(['h2', 'h3', 'h4', '.title', '.book-title'])
                if title_elements:
                    logger.info(f"{len(title_elements)} 件のタイトル要素が見つかりました")
                    # タイトル要素の親やその周辺から情報を抽出
                    for i, title_elem in enumerate(title_elements[:100]):  # 最大100件に制限
                        try:
                            # タイトル
                            title = title_elem.text.strip()
                            
                            # 著者 (タイトル要素の周辺または親の要素から探す)
                            author = "不明"
                            author_elem = None
                            
                            # 著者情報をタイトルの後の要素から探す
                            next_elems = list(title_elem.next_siblings)
                            for elem in next_elems:
                                if elem.name and elem.text and "作" in elem.text or "著" in elem.text:
                                    author_elem = elem
                                    break
                            
                            # 親要素からも著者情報を探す
                            if not author_elem and title_elem.parent:
                                for elem in title_elem.parent.find_all(text=True):
                                    if "作" in elem or "著" in elem:
                                        author = elem.strip()
                                        if ":" in author or "：" in author:
                                            author = author.split(":", 1)[1].strip()
                                        break
                            
                            if author_elem:
                                author = author_elem.text.strip()
                            
                            # 著者名をクリーンアップ（余計なテキストを削除）
                            author = self._clean_author_name(author)
                            
                            # マンガデータをリストに追加
                            manga_data.append({
                                'title': title,
                                'author': author,
                                'free_chapters': 0,  # 情報が見つからない場合はデフォルト値
                                'free_books': 0,     # 情報が見つからない場合はデフォルト値
                                'category_id': 'all', # デフォルトカテゴリ
                                'rank': i + 1        # 順番をランクとして使用
                            })
                            
                        except Exception as e:
                            logger.warning(f"アイテム解析中にエラーが発生しました (rank: {i+1}): {e}")
                
            else:
                # ランキングアイテムが見つかった場合、各アイテムからデータを抽出
                for i, item in enumerate(manga_items[:100]):  # 最大100件に制限
                    try:
                        # タイトル (様々なセレクタパターンを試す)
                        title = "不明"
                        for title_selector in ['.title', '.book-title', 'h2', 'h3', 'h4', 'a', '.name']:
                            title_elem = item.select_one(title_selector)
                            if title_elem and title_elem.text.strip():
                                title = title_elem.text.strip()
                                break
                        
                        # 一般的なテキストノードからタイトルを探す
                        if title == "不明":
                            for text in item.stripped_strings:
                                if len(text) > 5 and "作" not in text and "著" not in text:
                                    title = text
                                    break
                        
                        # 著者名の抽出
                        author = "不明"
                        
                        # 最初に指定されたHTMLクラスを持つ著者要素を探す
                        author_elem = item.select_one('.book-list--author')
                        if author_elem:
                            # 著者名を含むspanタグを探す
                            author_spans = author_elem.select('.book-list--author-item')
                            if author_spans:
                                # 著者名のリストを作成し、連結する
                                authors = [span.text.strip() for span in author_spans if span.text.strip()]
                                author = '・'.join(authors)
                                
                                # 「他」や「その他」などのテキストが末尾にある場合は追加
                                suffix = author_elem.text.strip()
                                if suffix.endswith('他') or suffix.endswith('ほか'):
                                    if not author.endswith('他') and not author.endswith('ほか'):
                                        author += ' 他'
                            else:
                                # spanがない場合は要素のテキスト全体を使用
                                author = author_elem.text.strip()
                        
                        # 上記で著者が見つからなければ、従来の方法を試す
                        if author == "不明":
                            # 一般的な著者セレクタを試す
                            for author_selector in ['.author', '.writer', '.creator', '.artist']:
                                author_elem = item.select_one(author_selector)
                                if author_elem and author_elem.text.strip():
                                    author = author_elem.text.strip()
                                    break
                            
                            # テキストから著者情報を探す
                            if author == "不明":
                                for text in item.stripped_strings:
                                    if "作" in text or "著" in text:
                                        author = text.strip()
                                        if ":" in author or "：" in author:
                                            author = author.split(":", 1)[1].strip()
                                        break
                        
                        # 著者名をクリーンアップ（余計なテキストを削除）
                        author = self._clean_author_name(author)
                        
                        # 無料話数と無料冊数の抽出
                        free_chapters = 0
                        free_books = 0
                        
                        # 指定された特定のクラスを持つasideタグを検索
                        free_book_elem = item.select_one('aside.icon-text.icon-text__jikkuri')
                        if free_book_elem and '冊無料' in free_book_elem.text:
                            # 「N冊無料」から数字を抽出
                            books_match = re.search(r'(\d+)冊無料', free_book_elem.text)
                            if books_match:
                                free_books = int(books_match.group(1))
                                logger.info(f"無料冊数を検出: {free_books}冊 (rank: {i+1})")
                        
                        # 無料話数の抽出（既存の方法も維持）
                        for text in item.stripped_strings:
                            # 無料話数
                            chapters_match = re.search(r'(\d+)話無料', text)
                            if chapters_match:
                                free_chapters = int(chapters_match.group(1))
                                
                            # 特定のクラスで見つからなかった場合の無料冊数の検索（バックアップ）
                            if free_books == 0 and '冊無料' in text:
                                books_match = re.search(r'(\d+)冊無料', text)
                                if books_match:
                                    free_books = int(books_match.group(1))
                        
                        # 他のセレクタパターンも試す（より一般的な方法）
                        if free_books == 0:
                            for book_selector in ['.free-volumes', '.volume-free', '.free-book']:
                                book_elem = item.select_one(book_selector)
                                if book_elem and '冊' in book_elem.text:
                                    books_match = re.search(r'(\d+)冊', book_elem.text)
                                    if books_match:
                                        free_books = int(books_match.group(1))
                                        break
                        
                        # カテゴリ
                        category_id = 'all'  # デフォルト
                        genre_patterns = {
                            'shounen': ['少年', 'しょうねん', 'ボーイズ'],
                            'shoujo': ['少女', 'しょうじょ', 'ガールズ'],
                            'seinen': ['青年', 'せいねん', 'メンズ'],
                            'josei': ['女性', 'じょせい', 'レディース']
                        }
                        
                        # 全てのテキストからジャンル情報を検索
                        full_text = ' '.join(item.stripped_strings)
                        for cat_id, patterns in genre_patterns.items():
                            for pattern in patterns:
                                if pattern in full_text:
                                    category_id = cat_id
                                    break
                            if category_id != 'all':
                                break
                        
                        # マンガデータをリストに追加
                        manga_data.append({
                            'title': title,
                            'author': author,
                            'free_chapters': free_chapters,
                            'free_books': free_books,
                            'category_id': category_id,
                            'rank': i + 1
                        })
                        
                    except Exception as e:
                        logger.warning(f"マンガアイテムの解析中にエラーが発生しました (rank: {i+1}): {e}")
            
            if manga_data:
                logger.info(f"合計 {len(manga_data)} 件のマンガデータを抽出しました")
            else:
                logger.warning("マンガデータを抽出できませんでした")
                
                # HTMLの特徴を分析してデバッグ情報を出力
                main_content = soup.find('main') or soup.find('div', id='content') or soup.find('div', class_='content')
                if main_content:
                    logger.info(f"メインコンテンツの子要素数: {len(list(main_content.children))}")
                    # 最初の数個の要素のクラス名をログ出力
                    for i, child in enumerate(list(main_content.children)[:5]):
                        if hasattr(child, 'name'):
                            logger.info(f"子要素 {i+1}: タグ={child.name}, クラス={child.get('class', 'なし')}")
                
            return manga_data
            
        except Exception as e:
            logger.error(f"スクレイピング中にエラーが発生しました: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
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