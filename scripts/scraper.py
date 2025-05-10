"""
マンガデータをスクレイピングするスクリプト
Django extensionsのrunscriptコマンドで実行する
例: python manage.py runscript scraper
"""
import time
import logging
from datetime import datetime, date
from django.db import transaction
from manga.models import Category, EbookStore, ScrapingHistory
from scripts.scrapers.registry import ScraperRegistry
from scripts.utils import get_or_create_manga

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run():
    """
    スクリプトのメインエントリポイント
    """
    logger.info("マンガデータスクレイピングを開始します")
    
    try:
        # カテゴリデータが存在しない場合は作成
        create_initial_categories()
        
        # 電子書籍ストアをすべて取得
        stores = get_active_stores()
        
        if not stores:
            logger.warning("アクティブな電子書籍ストアが見つかりません。スクレイピングをスキップします。")
            return
        
        # 各電子書籍ストアに対してスクレイピングを実行
        for store in stores:
            try:
                logger.info(f"電子書籍ストア '{store.name}' (ID: {store.id}) のスクレイピングを開始します")
                
                # スクレイピング履歴（同じ日付・ストアがあれば再利用、なければ作成）
                today = date.today()
                scraping_history, _ = ScrapingHistory.objects.get_or_create(
                    store=store,
                    scraping_date=today,
                    defaults={
                        'started_at': datetime.now(),
                        'is_success': False
                    }
                )
                
                # スクレイパーインスタンスを取得
                try:
                    scraper = ScraperRegistry.get_scraper(store.id)
                    
                    # スクレイピング履歴をインスタンスにセット
                    setattr(scraper, 'scraping_history', scraping_history)
                    
                    # スクレイピングを実行
                    success = scraper.run()
                    scraping_history.is_success = bool(success)
                    scraping_history.finished_at = datetime.now()
                    scraping_history.save()
                    
                    if success:
                        logger.info(f"電子書籍ストア '{store.name}' のスクレイピングが成功しました")
                    else:
                        logger.error(f"電子書籍ストア '{store.name}' のスクレイピングが失敗しました")
                
                except ValueError as e:
                    logger.error(f"電子書籍ストア '{store.name}' (ID: {store.id}) のスクレイパーが見つかりません: {e}")
                
                # スクレイパー間の待機時間（サーバー負荷軽減のため）
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"電子書籍ストア '{store.name}' のスクレイピング中にエラーが発生しました: {e}")
        
        logger.info("すべてのスクレイピングが完了しました")
    
    except Exception as e:
        logger.error(f"スクレイピング処理中にエラーが発生しました: {e}")
    
    # 注意: このスクリプトは通常、cron jobなどのスケジューラで1日1回実行するように設定します
    # 以下のwhileループはデバッグ用で、本番環境では削除してください
    """
    while True:
        logger.info(f"次回の実行まで待機中... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        time.sleep(3600)  # 1時間待機
    """


@transaction.atomic
def create_initial_categories():
    """初期カテゴリデータを作成"""
    if Category.objects.exists():
        logger.info("カテゴリデータは既に存在します")
        return
        
    categories = [
        {'id': 'all', 'name': '全て'},
        {'id': 'shounen', 'name': '少年マンガ'},
        {'id': 'shoujo', 'name': '少女マンガ'},
        {'id': 'seinen', 'name': '青年マンガ'},
        {'id': 'josei', 'name': '女性マンガ'},
    ]
    
    for cat_data in categories:
        Category.objects.create(id=cat_data['id'], name=cat_data['name'])
    
    logger.info(f"{len(categories)}件のカテゴリを作成しました")


def get_active_stores():
    """アクティブな電子書籍ストアを取得"""
    # deleted_atがNullのストアのみを取得（論理削除されていないストア）
    stores = EbookStore.objects.filter(deleted_at__isnull=True)
    logger.info(f"{len(stores)}件のアクティブな電子書籍ストアが見つかりました")
    return stores


if __name__ == "__main__":
    # スタンドアロンで実行する場合（テスト用）
    run()