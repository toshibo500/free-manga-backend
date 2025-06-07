from manga.models import Manga
import unicodedata

def get_or_create_manga(title, author, categories, cover_image=None, description=None, rating=0, first_book_title=None):
    """
    タイトルでマンガを検索し、なければ新規作成する共通関数
    タイトルは全て全角に変換して検索・登録します
    :param title: str
    :param author: str
    :param categories: list of Categoryインスタンス
    :param cover_image: str or None
    :param description: str or None
    :param rating: float
    :param first_book_title: str or None
    :return: Mangaインスタンス, created(bool)
    """
    # 追加バリデーション: 空やNone、空白のみ、または'不明'は作成しない
    if not title or title == "不明":
        return None, False
    if not isinstance(title, str) or not title.strip():
        return None, False
    
    # タイトルを全角に変換
    normalized_title = unicodedata.normalize('NFKC', title)
    
    # タイトルで検索
    existing_manga = Manga.objects.filter(title=normalized_title).first()
    
    if existing_manga:
        # 既存のマンガが見つかった場合は、それを返す
        if categories:
            existing_manga.categories.add(*categories)
        if first_book_title:
            existing_manga.first_book_title = first_book_title
            existing_manga.save()
        return existing_manga, False
    
    # 既存のマンガがない場合のみ新規作成
    # author のバリデーション
    if not author or author == "不明" or not isinstance(author, str) or not author.strip():
        return None, False
        
    manga = Manga.objects.create(
        title=normalized_title,
        author=author,
        cover_image=cover_image or '',
        description=description or '',
        rating=rating,
        first_book_title=first_book_title  # New field added
    )
    if categories:
        manga.categories.set(categories)
    return manga, True
