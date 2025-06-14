"""
マンガテーブルのRatingを更新するスクリプト

このスクリプトは、スクレイピングされたマンガデータの順位に基づいてRatingを更新します。

Usage:
    python manage.py runscript update_manga_ratings [--script-args="YYYY-MM-DD"]
    
    引数を省略した場合は当日のデータを使用します。
    
Example:
    python manage.py runscript update_manga_ratings
    python manage.py runscript update_manga_ratings --script-args="2025-05-10"
"""
import logging
from datetime import datetime, date
import sys
import os
import requests
from django.db import transaction
from django.db.models import Avg, Min, Max, Case, When, F, Value, IntegerField
from manga.models import Manga, ScrapedManga, ScrapingHistory, EbookStore

logger = logging.getLogger(__name__)

# Google Books APIのクォータ制限フラグ（グローバル変数）
google_books_quota_exceeded = False

def update_ratings(target_date=None):
    """
    指定された日付のスクレイピングデータに基づいてマンガのレーティングを更新します
    
    Args:
        target_date (date, optional): 集計対象日。指定しない場合は当日を使用します。
    
    Returns:
        int: 更新されたマンガの件数
    """
    # 対象日の設定（デフォルトは当日）
    if target_date is None:
        target_date = date.today()
    elif isinstance(target_date, str):
        # YYYY-MM-DD形式の文字列を日付オブジェクトに変換
        try:
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        except ValueError:
            logger.error(f"無効な日付形式です: {target_date}. 正しい形式はYYYY-MM-DDです。")
            return 0
    
    print(f"対象日: {target_date} (type: {type(target_date)})")
    logger.info(f"対象日 {target_date} のスクレイピングデータに基づいてRatingを更新します")
    
    # 全てのスクレイピング履歴を表示
    all_histories = ScrapingHistory.objects.all()
    print(f"データベース内の全スクレイピング履歴: {all_histories.count()}件")
    for h in all_histories:
        print(f"- 日付: {h.scraping_date} (type: {type(h.scraping_date)}), ストア: {h.store.name}, 成功: {h.is_success}")
    
    # 対象日のスクレイピング履歴を取得
    histories = ScrapingHistory.objects.filter(
        scraping_date=target_date,
        is_success=True
    )
    print(f"対象日のスクレイピング履歴: {histories.count()}件")
    
    if not histories.exists():
        logger.warning(f"対象日 {target_date} の成功したスクレイピング履歴が見つかりません")
        return 0
    
    # 全ストアのデータを取得
    stores = [h.store for h in histories]
    store_names = ", ".join([s.name for s in stores])
    logger.info(f"ストア ({store_names}) のスクレイピングデータを使用します")
    
    # トランザクション内でRatingを更新
    with transaction.atomic():
        # すべてのマンガを取得
        mangas = Manga.objects.all()
        
        # 更新対象のマンガの総数
        manga_count = mangas.count()
        logger.info(f"更新対象のマンガ: {manga_count}件")
        
        updated_count = 0
        
        # 各マンガのRatingを計算して更新
        for manga in mangas:
            # 該当日のスクレイピングデータをすべて取得
            scraped_data = ScrapedManga.objects.filter(
                manga=manga,
                scraping_history__in=histories
            )
            
            if not scraped_data.exists():
                # 順位データがない場合はスキップ
                print(f"マンガ「{manga.title}」の順位データがありません")
                continue
            
            print(f"マンガ「{manga.title}」のスクレイピングデータ: {scraped_data.count()}件")
            
            # 各スクレイピングデータの合計を計算
            # 1位 1000点
            # 2位 750点
            # 3位 500点
            # 4位 300点
            # 5位 250点
            # 6位 200点
            # 7位 175点
            # 8位 150点
            # 9位 125点
            # 10位 100点
            # 11位以下 100-順位点
            # ただし、順位が100以上の場合は0点
            total_rating = 0
            ranks_info = []
            
            for data in scraped_data:
                print(f"  - スクレイピングID: {data.id}, 順位: {data.rank}, ストア: {data.scraping_history.store.name}")
                if data.rank == 1:
                    points = 1000
                elif data.rank == 2:
                    points = 750
                elif data.rank == 3:
                    points = 500
                elif data.rank == 4:
                    points = 300
                elif data.rank == 5:
                    points = 250
                elif data.rank == 6:
                    points = 200
                elif data.rank == 7:
                    points = 175
                elif data.rank == 8:
                    points = 150
                elif data.rank == 9:
                    points = 125
                elif data.rank == 10:
                    points = 100
                elif data.rank >= 11:
                    points = max(0, 100 - data.rank)
                else:
                    points = 0
                total_rating += points
                ranks_info.append(f"{data.scraping_history.store.name} (順位: {data.rank}, 点数: {points})")
            print(f"  合計Rating: {total_rating}")
            
            # 新しいRating値（最大100000に制限）
            if total_rating > 100000:
                new_rating = 100000
            else:
                new_rating = int(total_rating)
            
            print(f"  計算されたRating: {new_rating}, 現在のRating: {manga.rating}, 型: {type(manga.rating)}")
            
            # 無料話数と無料巻数の計算（最大値を使用）
            free_chapters = scraped_data.aggregate(max_chapters=Max('free_chapters'))['max_chapters'] or 0
            free_books = scraped_data.aggregate(max_books=Max('free_books'))['max_books'] or 0
            
            # Ratingまたは無料話数/無料巻数の更新が必要かチェック
            needs_update = (manga.rating != new_rating or 
                           manga.free_chapters != free_chapters or 
                           manga.free_books != free_books)
                           
            if needs_update:
                # 値を更新
                old_rating = manga.rating
                old_free_chapters = manga.free_chapters
                old_free_books = manga.free_books
                
                manga.rating = new_rating
                manga.free_chapters = free_chapters
                manga.free_books = free_books
                
                # 更新するフィールドを指定
                manga.save(update_fields=['rating', 'free_chapters', 'free_books'])
                updated_count += 1
                
                ranks_detail = ", ".join(ranks_info)
                logger.info(f"マンガ「{manga.title}」の更新: Rating: {old_rating} -> {new_rating}, "
                           f"無料話数: {old_free_chapters} -> {free_chapters}, "
                           f"無料巻数: {old_free_books} -> {free_books} "
                           f"(順位詳細: {ranks_detail})")
        
        logger.info(f"更新されたマンガ: {updated_count}/{manga_count}件")
        return updated_count

def fetch_google_books_data(first_book_title, title):
    """
    Google Books APIを使用して表紙画像、概要、ISBNコードを取得します。

    Args:
        first_book_title (str): マンガの第1巻タイトル
        title (str): マンガのタイトル

    Returns:
        dict: APIレスポンスデータ
    """
    global google_books_quota_exceeded
    
    # クォータが既に超過している場合はAPIを呼び出さない
    if google_books_quota_exceeded:
        logger.info(f"Google Books APIクォータ超過により、{title}のAPI呼び出しをスキップします")
        return None
    
    api_key = os.getenv('GOOGLE_BOOKS_API_KEY')
    if not api_key:
        logger.error("Google Books APIキーが設定されていません")
        return None

    # 初回リクエスト
    url = f"https://www.googleapis.com/books/v1/volumes?q=%2Bintitle%3A{first_book_title}%2Bintitle%3A%EF%BC%91&startIndex=0&maxResults=1&key={api_key}&langRestrict=ja-JP"
    try:
        print(f"Google Books APIを呼び出します: {url}")
        logger.info(f"Google Books APIを呼び出します: {url}")
        response = requests.get(url)
        
        # 429エラー（Too Many Requests）をチェック
        if response.status_code == 429:
            logger.warning("Google Books APIクォータ制限に達しました。以降のAPI呼び出しを停止します。")
            google_books_quota_exceeded = True
            return None
        
        response.raise_for_status()
        data = response.json()

        # itemsが取得できない、もしくは0件の場合は再試行
        if not data.get('items'):
            # 3から8秒の待機時間を追加
            import time
            wait_time = 3 + (5 * (hash(first_book_title) % 2))  # ハッシュ値を使用して待機時間を変動
            logger.warning(f"Google Books APIで結果が見つかりませんでした。{wait_time}秒待機してタイトルで再試行します")
            time.sleep(wait_time)
            print("Google Books APIで結果が見つかりませんでした。タイトルで再試行します")
            url = f"https://www.googleapis.com/books/v1/volumes?q=%2Bintitle%3A{title}&startIndex=0&maxResults=1&key={api_key}&langRestrict=ja-JP"
            logger.info(f"Google Books APIを再試行します: {url}")
            response = requests.get(url)
            
            # 再度429エラーをチェック
            if response.status_code == 429:
                logger.warning("Google Books APIクォータ制限に達しました。以降のAPI呼び出しを停止します。")
                google_books_quota_exceeded = True
                return None
            
            response.raise_for_status()
            data = response.json()
        else:
            logger.info("Google Books APIからデータを取得しました") 

        return data

    except requests.RequestException as e:
        if "429" in str(e):
            logger.warning("Google Books APIクォータ制限に達しました。以降のAPI呼び出しを停止します。")
            google_books_quota_exceeded = True
        else:
            logger.error(f"Google Books APIの呼び出し中にエラーが発生しました: {e}")
        return None

def run(*args):
    """
    スクリプト実行のエントリーポイント
    
    Args:
        args: コマンドライン引数（対象日）
    """
    # デバッグ用に標準出力にもメッセージを出力
    print("スクリプト実行開始")
    
    # 対象日の取得（指定がなければ当日）
    target_date = None
    if args and len(args) > 0:
        target_date = args[0]
        print(f"指定された対象日: {target_date}")
        logger.info(f"指定された対象日: {target_date}")
    else:
        print("対象日の指定がないため、当日のデータを使用します")
        logger.info("対象日の指定がないため、当日のデータを使用します")
    
    try:
        # Ratingの更新処理を実行
        print("更新処理を実行します...")
        updated_count = update_ratings(target_date)
        print(f"Rating更新処理が完了しました。更新件数: {updated_count}件")
        logger.info(f"Rating更新処理が完了しました。更新件数: {updated_count}件")
        
        # Google Books APIからデータを取得
        google_books_updates = 0
        skipped_due_to_quota = 0
        
        for manga in Manga.objects.all():
            # クォータ制限チェック
            if google_books_quota_exceeded:
                skipped_due_to_quota += 1
                continue
                
            # マンガの第1巻タイトルとタイトルを使用してGoogle Books APIからデータを取得
            # first_book_titleが空の場合はタイトルのみで検索
            google_books_data = fetch_google_books_data(
                manga.first_book_title or manga.title,
                manga.title
            )
            if google_books_data and google_books_data.get('items'):
                volume_info = google_books_data['items'][0].get('volumeInfo', {})
                manga.description = volume_info.get('description', manga.description)
                image_links = volume_info.get('imageLinks', {})
                manga.cover_image = image_links.get('thumbnail', manga.cover_image)
                manga.save(update_fields=['description', 'cover_image'])
                google_books_updates += 1
            # 3から8秒の待機時間を追加
            import time
            time.sleep(3 + (5 * (manga.id % 2)))
        
        print("Google Booksデータの取得とマンガ情報の更新が完了しました")
        print(f"Google Books情報更新件数: {google_books_updates}件")
        if google_books_quota_exceeded:
            print(f"クォータ制限によりスキップされた件数: {skipped_due_to_quota}件")
        logger.info("Google Booksデータの取得とマンガ情報の更新が完了しました")
        logger.info(f"Google Books情報更新件数: {google_books_updates}件")
        if google_books_quota_exceeded:
            logger.warning(f"Google Books APIクォータ制限により{skipped_due_to_quota}件がスキップされました")
        
        # 明示的に戻り値を指定しない（Noneを返す）
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        print(traceback.format_exc())
        logger.error(f"Rating更新処理中にエラーが発生しました: {e}")
        logger.error(traceback.format_exc())
        raise  # 例外を再スローして、エラーを明示的に示す
    
    return None

if __name__ == "__main__":
    # コマンドライン引数から対象日を取得
    target_date = None
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    run(target_date)
