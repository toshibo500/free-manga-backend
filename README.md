# Free Manga API

Django REST Framework と MySQL8 を使用したマンガ情報API

## 機能

- マンガ情報の取得API (`/api/v1/manga/{id}`)
- カテゴリ別の人気マンガリスト取得API (`/api/v1/manga/popular-books/{category}`)
- スクレイピングジョブによるマンガデータの自動収集

## 技術スタック

- Django 3.2
- Django REST Framework
- MySQL 8.0
- Docker & Docker Compose

## 開発環境のセットアップ

### 前提条件

- Docker と Docker Compose がインストールされていること

### インストール手順

1. リポジトリをクローン
   ```
   git clone [リポジトリURL]
   cd free-manga-api
   ```

2. Docker コンテナのビルドと起動
   ```
   docker-compose up -d
   ```

3. データベースのマイグレーション
   ```
   docker-compose exec api python manage.py migrate
   ```

4. 管理者ユーザーの作成
   ```
   docker-compose exec api python manage.py createsuperuser
   ```

5. スクレイピングジョブの実行（初期データ作成）
   ```
   docker-compose exec api python manage.py runscript scraper
   ```
   
## アクセス方法

- API: http://localhost:8000/api/v1/
- API ドキュメント: http://localhost:8000/swagger/
- 管理画面: http://localhost:8000/admin/

## APIエンドポイント

### マンガ詳細の取得

```
GET /api/v1/manga/{id}/
```

### カテゴリ別人気マンガリストの取得

```
GET /api/v1/manga/popular-books/{category}/
```

利用可能なカテゴリ:
- all: 全て
- shounen: 少年マンガ
- shoujo: 少女マンガ
- seinen: 青年マンガ
- josei: 女性マンガ

## 開発

### 新しいアプリケーションの追加

```
docker-compose exec api python manage.py startapp [アプリ名]
```

### マイグレーションの作成

```
docker-compose exec api python manage.py makemigrations
```

### テストの実行

```
docker-compose exec api python manage.py test
```

## スクレイピングジョブについて

スクレイピングジョブはプロセスとして常時稼働し、1時間ごとにデータを更新します。
実際のスクレイピングロジックは `scripts/scraper.py` に実装してください。

## ライセンス

[ライセンス情報]