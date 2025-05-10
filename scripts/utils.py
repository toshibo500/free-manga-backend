from manga.models import Manga

def get_or_create_manga(title, author, categories, cover_image=None, description=None, rating=0.0):
    """
    タイトルでマンガを検索し、なければ新規作成する共通関数
    :param title: str
    :param author: str
    :param categories: list of Categoryインスタンス
    :param cover_image: str or None
    :param description: str or None
    :param rating: float
    :return: Mangaインスタンス, created(bool)
    """
    # 追加バリデーション: 空やNone、空白のみ、または'不明'は作成しない
    if not title or not author or title == "不明" or author == "不明":
        return None, False
    if not isinstance(title, str) or not isinstance(author, str) or not title.strip() or not author.strip():
        return None, False

    manga, created = Manga.objects.get_or_create(
        title=title,
        author=author,
        defaults={
            'cover_image': cover_image or '',
            'description': description or '',
            'rating': rating,
            'free_chapters': 0,
            'free_books': 0,
        }
    )
    if created and categories:
        manga.categories.set(categories)
    elif not created and categories:
        manga.categories.add(*categories)
    return manga, created
