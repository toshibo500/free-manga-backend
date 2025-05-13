"""
特定のスクレイパーをテストモードで実行するスクリプト
Django extensionsのrunscriptコマンドで実行する
例: python manage.py runscript test_scraper --script-args="ebookstore_a"
    python manage.py runscript test_scraper --script-args="ebookstore_b"
    python manage.py runscript test_scraper --script-args="ebookstore_c"
"""
import logging
import sys
from django.db import transaction
from manga.models import EbookStore, ScrapingHistory
from scripts.scrapers.registry import ScraperRegistry
from datetime import datetime

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# スクレイパー名と対応するストア名のマッピング
SCRAPER_STORE_MAPPINGS = {
    "ebookstore_a": "まんが王国",  # ID: 1
    "ebookstore_b": "スキマ",      # ID: 2
    "ebookstore_c": "ebook japan", # ID: 3
    "ebookstore_d": "シーモア"     # ID: 4
}

def run(*args):
    """
    テスト用スクリプトのメインエントリポイント
    
    Args:
        args: スクリプト引数 (最初の引数は scraper_name)
    """
    if not args or len(args) < 1:
        logger.error("スクレイパー名を指定してください。例: python manage.py runscript test_scraper --script-args=\"ebookstore_c\"")
        return
    
    scraper_name = args[0].lower()
    
    # サポートされているスクレイパーかチェック
    if scraper_name not in SCRAPER_STORE_MAPPINGS:
        logger.error(f"サポートされていないスクレイパー名: {scraper_name}")
        logger.error(f"サポートされているスクレイパー: {', '.join(SCRAPER_STORE_MAPPINGS.keys())}")
        return
        
    logger.info(f"スクレイパー '{scraper_name}' をテストモードで実行します")
    
    try:
        store_name = SCRAPER_STORE_MAPPINGS[scraper_name]
        
        # ストアIDを取得
        store = EbookStore.objects.filter(name__icontains=store_name).first()
        if not store:
            logger.error(f"{store_name}の電子書籍ストアが見つかりません。")
            return
        
        store_id = store.id
        logger.info(f"{store_name}の電子書籍ストア (ID: {store_id}) を使用します")
        
        # テスト用のスクレイピング履歴を取得または作成
        from datetime import date
        today = date.today()
        
        # 既存の履歴があれば取得、なければ作成
        scraping_history, created = ScrapingHistory.objects.get_or_create(
            store=store,
            scraping_date=today,
            defaults={
                'started_at': datetime.now(),
                'is_success': False,
            }
        )
        
        if not created:
            # 既存の履歴を再利用する場合は開始時間を更新
            scraping_history.started_at = datetime.now()
            scraping_history.is_success = False
            scraping_history.error_message = ""
            scraping_history.finished_at = None
            scraping_history.save()
            
        logger.info(f"スクレイピング履歴 ID: {scraping_history.id} ({'新規作成' if created else '再利用'})")
        
        # スクレイパーレジストリからスクレイパーを取得
        try:
            # スクレイパーインスタンスを取得
            scraper = ScraperRegistry.get_scraper(store_id)
            setattr(scraper, 'scraping_history', scraping_history)
        except ValueError as e:
            logger.error(f"ストアID {store_id} に対応するスクレイパーが見つかりません: {e}")
            return
        
        # テストモード用の設定を追加（処理件数を制限）
        setattr(scraper, 'test_mode', True)
        setattr(scraper, 'test_item_limit', 5)  # 5件のみ処理
        
        # 制限付きでスクレイピング実行 (テストモードなので一部データのみ)
        logger.info(f"テストモードでスクレイピング実行（5件のみ処理）")
        success = scraper.run()
        
        # スクレイピング履歴を更新
        scraping_history.is_success = bool(success)
        scraping_history.finished_at = datetime.now()
        scraping_history.save()
        
        if success:
            logger.info(f"{store_name}のスクレイピングテストが正常に完了しました")
        else:
            logger.error(f"{store_name}のスクレイピングテストが失敗しました")
    except Exception as e:
        logger.error(f"テスト実行中にエラーが発生しました: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    # 引数がある場合はそれを使用、ない場合はデフォルト値
    args = sys.argv[1:] if len(sys.argv) > 1 else ["ebookstore_b"]
    run(*args)
