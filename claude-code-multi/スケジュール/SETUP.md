# Google Calendar 連携 セットアップ手順

## 1. ライブラリをインストール

```bash
pip3 install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

## 2. Google Cloud Console で認証情報を作成

1. https://console.cloud.google.com/ にアクセス
2. 新規プロジェクトを作成（例：`noah-axice-calendar`）
3. 左メニュー → 「APIとサービス」→「ライブラリ」
4. 「Google Calendar API」を検索して有効化
5. 「APIとサービス」→「認証情報」→「認証情報を作成」→「OAuthクライアントID」
6. アプリケーションの種類：**デスクトップアプリ**
7. 作成後「JSONをダウンロード」
8. ダウンロードしたファイルを `スケジュール/credentials.json` に名前を変えて保存

## 3. 初回認証（一度だけ）

```bash
cd claude-code-multi/スケジュール
python3 gcal_add.py "テスト" "2026-04-10"
```

ブラウザが開くのでGoogleアカウントでログイン → 許可する。
以降は自動で認証される（`token.json` が保存される）。

---

## 使い方

### 個別に登録する

```bash
# 終日予定
python3 gcal_add.py "講師にDM" "2026-04-15"

# 時間指定
python3 gcal_add.py "体験レッスン" "2026-05-28" --time "15:00" --end "16:00" --desc "千里コミュニティセンター"
```

### カレンダー.md から一括登録

```bash
python3 gcal_add.py --sync
```

---

## 注意

- `credentials.json` と `token.json` はGitにコミットしない（.gitignore済み）
- token.json は自動生成されるので削除しても再認証で再生成できる
