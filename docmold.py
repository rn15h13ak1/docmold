#!/usr/bin/env python3
"""docmold - Markdown を、内容の種類ごとに表現を変えた自己完結 HTML に変換する。

Usage:
    python docmold.py 議事録.md                    # front matter の type で表現が決まる
    python docmold.py docs/ -o out/ --index        # ディレクトリ再帰 + 索引 HTML
    python docmold.py 手順.md --type procedure     # front matter を書き換えずに別表現で出す
    python docmold.py --list-types                 # 指定できる種類の一覧
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
# フルパス実行 (python /abs/path/docmold.py) でも sibling モジュールを解決できるようにする。
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
