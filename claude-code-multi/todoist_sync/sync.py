#!/usr/bin/env python3
"""
Todoist ↔ tasks.md 双方向同期スクリプト

使い方:
  python sync.py pull   # Todoist → tasks.md（セッション開始時に自動実行）
  python sync.py push   # tasks.md → Todoist（タスク編集後に自動実行）

権威の分離ルール（事故防止）:
  - タスクの「状態」（完了・削除）は Todoist が権威
  - タスクの「内容・構造」は tasks.md が権威
  - コンテンツの自動上書きはしない
"""

import json
import os
import re
import sys
import uuid
from pathlib import Path

try:
    import requests
except ImportError:
    print("⚠ requests が未インストールです: pip install requests")
    sys.exit(1)

# ── 設定 ────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / ".env"
TASKS_MD = BASE_DIR / "タスク台帳" / "tasks.md"
PROJECT_NAME = "Noah Axice"
API_BASE = "https://api.todoist.com/rest/v2"

# tasks.md セクション見出し → Todoist セクション名
SECTION_MAP = {
    "👤 会長（あつき）アクション待ち": "会長タスク",
    "💃 ダンス事業部": "ダンス事業部",
    "💰 経理部": "経理部",
    "🏗️ プロジェクト統括部": "プロジェクト統括部",
    "🧠 CEO": "CEO",
    "🤝 キャスティング部": "キャスティング部",
    "👥 採用": "採用",
}
SECTION_MAP_INV = {v: k for k, v in SECTION_MAP.items()}

# ── 環境変数 ─────────────────────────────────────────────────────────────────

def load_env():
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

def get_token():
    t = os.environ.get("TODOIST_API_TOKEN", "")
    if not t:
        print("❌ TODOIST_API_TOKEN が未設定です。.env を確認してください。")
        sys.exit(1)
    return t

def auth_headers():
    return {
        "Authorization": f"Bearer {get_token()}",
        "Content-Type": "application/json",
    }

# ── Todoist API ──────────────────────────────────────────────────────────────

def api_get(path, params=None):
    r = requests.get(f"{API_BASE}/{path}", headers=auth_headers(), params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def api_post(path, data=None):
    r = requests.post(
        f"{API_BASE}/{path}",
        headers={**auth_headers(), "X-Request-Id": str(uuid.uuid4())},
        json=data,
        timeout=10,
    )
    r.raise_for_status()
    return r.json() if r.text else {}

def get_or_create_project():
    for p in api_get("projects"):
        if p["name"] == PROJECT_NAME:
            return p["id"]
    return api_post("projects", {"name": PROJECT_NAME})["id"]

def get_or_create_sections(project_id):
    """セクションキャッシュ {name: id} を返す。なければ作成。"""
    existing = {s["name"]: s["id"] for s in api_get("sections", {"project_id": project_id})}
    for td_name in SECTION_MAP.values():
        if td_name not in existing:
            s = api_post("sections", {"project_id": project_id, "name": td_name})
            existing[td_name] = s["id"]
    return existing

def get_active_tasks(project_id):
    return {t["id"]: t for t in api_get("tasks", {"project_id": project_id})}

# ── tasks.md パーサー ────────────────────────────────────────────────────────

TID_RE      = re.compile(r'\s*<!--tid:(\w+)-->')
DEADLINE_RE = re.compile(r'（期限：([^）]+)）')
SECTION_RE  = re.compile(r'^##\s+(.+)')
STATUS_RE   = re.compile(r'\[([ x~!])\]')
STATUS_MAP  = {" ": "pending", "x": "done", "~": "in_progress", "!": "blocked"}

def parse_tasks_md(content):
    lines = content.splitlines()
    tasks = []
    current_section = None
    for i, line in enumerate(lines):
        m = SECTION_RE.match(line)
        if m:
            current_section = m.group(1).strip()
            continue
        if not (line.startswith("- [") and current_section):
            continue
        sm = STATUS_RE.search(line)
        if not sm:
            continue
        status = STATUS_MAP.get(sm.group(1), "pending")
        tid_m  = TID_RE.search(line)
        tid    = tid_m.group(1) if tid_m else None
        due_m  = DEADLINE_RE.search(line)
        due    = due_m.group(1) if due_m else None
        # メタデータを除いたクリーンなタスク内容
        bracket_end = line.index("]") + 2
        clean = TID_RE.sub("", line[bracket_end:]).strip()
        tasks.append({
            "section": current_section,
            "status": status,
            "content": clean,
            "tid": tid,
            "due": due,
            "line_idx": i,
        })
    return tasks, lines

def find_section_insert_point(lines, section_name):
    """セクション内の最後のタスク行インデックスを返す（末尾挿入用）"""
    last_task_idx = None
    in_target = False
    for i, line in enumerate(lines):
        m = SECTION_RE.match(line)
        if m:
            if in_target:
                break  # 次のセクションに入った
            if m.group(1).strip() == section_name:
                in_target = True
        elif in_target and line.startswith("- ["):
            last_task_idx = i
    return last_task_idx  # None = セクション見つからず

# ── Push: tasks.md → Todoist ─────────────────────────────────────────────────

def push():
    """tasks.md の変更を Todoist に反映する。
    - tid なし → Todoist に新規作成し、tasks.md に ID を書き戻す
    - [x] マーク → Todoist のタスクを完了にする
    """
    content = TASKS_MD.read_text(encoding="utf-8")
    tasks, lines = parse_tasks_md(content)

    project_id = get_or_create_project()
    sections   = get_or_create_sections(project_id)
    active     = get_active_tasks(project_id)
    modified   = False

    for task in tasks:
        if task["tid"]:
            # 既存タスク: 完了だけ同期（内容の上書きはしない）
            if task["tid"] in active and task["status"] == "done":
                api_post(f"tasks/{task['tid']}/close")
                print(f"  ✓ 完了: {task['content'][:45]}")
        else:
            # 新規タスク: Todoistに作成
            if task["status"] == "done":
                continue
            payload = {"content": task["content"], "project_id": project_id}
            td_sec = SECTION_MAP.get(task["section"])
            if td_sec and td_sec in sections:
                payload["section_id"] = sections[td_sec]
            if task["due"] and task["due"] not in ("未定",) and "確定後" not in task["due"]:
                payload["due_string"] = task["due"]
            new_task = api_post("tasks", payload)
            lines[task["line_idx"]] = lines[task["line_idx"]].rstrip() + f" <!--tid:{new_task['id']}-->"
            modified = True
            print(f"  ➕ 作成: {task['content'][:45]}")

    if modified:
        TASKS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("✅ Push 完了")

# ── Pull: Todoist → tasks.md ─────────────────────────────────────────────────

def pull():
    """Todoist の最新状態を tasks.md に反映する。
    - Todoist で完了/削除 → tasks.md を [x] に変更
    - Todoist にしかないタスク → tasks.md に追記
    """
    content = TASKS_MD.read_text(encoding="utf-8")
    tasks, lines = parse_tasks_md(content)

    project_id   = get_or_create_project()
    sections     = get_or_create_sections(project_id)
    sections_inv = {v: k for k, v in sections.items()}  # section_id → Todoist section name
    active       = get_active_tasks(project_id)

    md_tids = {t["tid"] for t in tasks if t["tid"]}
    result  = list(lines)
    changed = False

    # 1. Todoistから消えた（完了/削除）→ tasks.md を [x] に
    for task in tasks:
        if task["tid"] and task["tid"] not in active and task["status"] != "done":
            result[task["line_idx"]] = STATUS_RE.sub("[x]", result[task["line_idx"]], count=1)
            print(f"  ✓ 完了マーク: {task['content'][:45]}")
            changed = True

    # 2. Todoistにしかないタスク → 該当セクションの末尾に追加
    new_by_section = {}
    for tid, td in active.items():
        if tid in md_tids:
            continue
        td_sec_id   = td.get("section_id")
        td_sec_name = sections_inv.get(td_sec_id, "") if td_sec_id else ""
        md_sec      = SECTION_MAP_INV.get(td_sec_name, "👤 会長（あつき）アクション待ち")
        due         = td.get("due") or {}
        due_str     = due.get("date", "未定")
        new_line    = f"- [ ] {td['content']}（期限：{due_str}） <!--tid:{tid}-->"
        new_by_section.setdefault(md_sec, []).append(new_line)
        print(f"  ➕ 追加: {td['content'][:45]}")
        changed = True

    if new_by_section:
        # 後ろから処理することでインデックスがずれない
        sections_sorted = sorted(
            new_by_section.keys(),
            key=lambda s: find_section_insert_point(result, s) or 0,
            reverse=True,
        )
        for sec in sections_sorted:
            insert_at = find_section_insert_point(result, sec)
            if insert_at is not None:
                for j, line in enumerate(new_by_section[sec]):
                    result.insert(insert_at + 1 + j, line)
            else:
                # セクションがなければ末尾に追加
                result.append(f"\n## {sec}")
                result.extend(new_by_section[sec])

    if changed:
        TASKS_MD.write_text("\n".join(result) + "\n", encoding="utf-8")
    print("✅ Pull 完了")

# ── メイン ────────────────────────────────────────────────────────────────────

def main():
    load_env()

    # PostToolUse hook 経由の場合: tasks.md 以外の編集はスキップ
    if not sys.stdin.isatty():
        try:
            data = json.loads(sys.stdin.buffer.read())
            fp   = (data.get("tool_input") or {}).get("file_path", "")
            if "tasks.md" not in fp:
                sys.exit(0)
        except Exception:
            pass  # stdin が JSON でなければ続行

    cmd = sys.argv[1] if len(sys.argv) > 1 else "pull"

    try:
        if cmd == "pull":
            pull()
        elif cmd == "push":
            push()
        else:
            print(f"❌ 不明なコマンド: {cmd}  (pull / push)")
            sys.exit(1)
    except requests.RequestException as e:
        print(f"⚠ Todoist API エラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
