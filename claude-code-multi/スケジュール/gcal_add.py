#!/usr/bin/env python3
"""
Noah Axice | Google Calendar 登録スクリプト
使い方:
  python3 gcal_add.py "タイトル" "2026-05-31" --time "19:00" --end "20:00" --desc "詳細"
  python3 gcal_add.py --sync   # カレンダー.md の予定を一括登録
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"
CALENDAR_MD = Path(__file__).parent / "カレンダー.md"

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("依存ライブラリが未インストールです。以下を実行してください：")
        print("  pip3 install google-api-python-client google-auth-httplib2 google-auth-oauthlib")
        sys.exit(1)

    if not CREDENTIALS_FILE.exists():
        print(f"認証ファイルが見つかりません: {CREDENTIALS_FILE}")
        print("Google Cloud Console から credentials.json をダウンロードして同じフォルダに置いてください。")
        print("手順: スケジュール/SETUP.md を参照")
        sys.exit(1)

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def add_event(service, title, date_str, start_time=None, end_time=None, description=""):
    """Google カレンダーにイベントを追加する"""
    if start_time:
        start_dt = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %H:%M")
        if end_time:
            end_dt = datetime.strptime(f"{date_str} {end_time}", "%Y-%m-%d %H:%M")
        else:
            end_dt = start_dt + timedelta(hours=1)
        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Tokyo"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Tokyo"},
        }
    else:
        # 終日イベント
        event = {
            "summary": title,
            "description": description,
            "start": {"date": date_str},
            "end": {"date": date_str},
        }

    result = service.events().insert(calendarId="primary", body=event).execute()
    print(f"✅ 登録完了: {title} ({date_str})")
    print(f"   URL: {result.get('htmlLink')}")
    return result


def sync_from_md(service):
    """カレンダー.md から予定を読み込んで一括登録"""
    if not CALENDAR_MD.exists():
        print("カレンダー.md が見つかりません")
        sys.exit(1)

    lines = CALENDAR_MD.read_text(encoding="utf-8").splitlines()
    count = 0
    for line in lines:
        # テーブル行を解析: | 2026-04-15 | 水 | タイトル | 詳細 | 状態 |
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 4:
            continue
        date_str = cols[0]
        title = cols[2]
        description = cols[3]
        state = cols[4] if len(cols) > 4 else ""

        # 日付形式チェック (YYYY-MM-DD)
        if not date_str or not date_str[0].isdigit() or "末" in date_str or "〜" in date_str:
            continue
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        if "[完了]" in state:
            continue

        add_event(service, title, date_str, description=description)
        count += 1

    print(f"\n合計 {count} 件を登録しました。")


def main():
    parser = argparse.ArgumentParser(description="Noah Axice Google Calendar 登録ツール")
    parser.add_argument("title", nargs="?", help="予定のタイトル")
    parser.add_argument("date", nargs="?", help="日付 (YYYY-MM-DD)")
    parser.add_argument("--time", help="開始時間 (HH:MM)")
    parser.add_argument("--end", help="終了時間 (HH:MM)")
    parser.add_argument("--desc", default="", help="詳細・メモ")
    parser.add_argument("--sync", action="store_true", help="カレンダー.md から一括登録")
    args = parser.parse_args()

    service = get_service()

    if args.sync:
        sync_from_md(service)
    elif args.title and args.date:
        add_event(service, args.title, args.date, args.time, args.end, args.desc)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
