"""
マンガテーブルのRatingを更新するスクリプト

このスクリプトは、スクレイピングされたマンガデータの順位に基づいてRatingを更新します。
計算式: 各マンガの全スクレイピングデータの (100 - 順位) の合計

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
from django.db import transaction
from django.db.models import Avg, Min, Case, When, F, Value, IntegerField
from manga.models import Manga, ScrapedManga, ScrapingHistory, EbookStore

logger = logging.getLogger(__name__)

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
            
            # 各スクレイピングデータの(100 - 順位)の合計を計算
            total_rating = 0
            ranks_info = []
            
            for data in scraped_data:
                print(f"  - スクレイピングID: {data.id}, 順位: {data.rank}, ストア: {data.scraping_history.store.name}")
                rank_score = max(100 - data.rank, 0)  # マイナスにならないよう保証
                total_rating += rank_score
                ranks_info.append(f"{data.rank}位({rank_score}点)")
            
            # 新しいRating値（最大999に制限）
            if total_rating > 999:
                new_rating = 999
            else:
                new_rating = int(total_rating)
            
            print(f"  計算されたRating: {new_rating}, 現在のRating: {manga.rating}, 型: {type(manga.rating)}")
            
            # 現在のRatingと比較して、変更がある場合のみ更新
            if manga.rating != new_rating:
                # Ratingを更新
                old_rating = manga.rating
                manga.rating = new_rating
                manga.save(update_fields=['rating'])
                updated_count += 1
                ranks_detail = ", ".join(ranks_info)
                logger.info(f"マンガ「{manga.title}」のRating更新: {old_rating} -> {new_rating} (順位詳細: {ranks_detail})")
        
        logger.info(f"更新されたマンガ: {updated_count}/{manga_count}件")
        return updated_count

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
