"""依存パッケージの確認と、足りないときの案内。

インタプリタを取り違えたときに、トレースバックではなく
「どの Python で動いていて、何を入れればよいか」を出すためのモジュール。
そのため **サードパーティを import しない**（このモジュール自体が落ちては意味がない）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import List

SCRIPT_DIR = Path(__file__).resolve().parent

#: import 名 → requirements.txt 上の名前。無いと変換できない。
REQUIRED = {
    "markdown": "Markdown",
    "jinja2": "Jinja2",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
}

#: 無くても動くもの（コードハイライトが無効になるだけ）。
OPTIONAL = {
    "pygments": "Pygments",
}


def missing(names: dict = None) -> List[str]:
    """入っていないパッケージを requirements.txt 上の名前で返す。"""
    targets = REQUIRED if names is None else names
    return [
        package for module, package in targets.items()
        if importlib.util.find_spec(module) is None
    ]


def explain(packages: List[str]) -> str:
    """不足しているときの案内文を組み立てる。"""
    requirements = SCRIPT_DIR / "requirements.txt"
    lines = [
        "必要なライブラリが入っていません: " + ", ".join(packages),
        "",
        f"  実行中の Python: {sys.executable}",
        "",
        "次のいずれかで解決できます。",
        "",
        "  1) この Python に入れる",
        f"     {sys.executable} -m pip install -r {requirements}",
        "",
        "  2) 依存が入っている Python で実行する",
        "     Anaconda を使う場合は Anaconda Prompt から実行してください。",
    ]
    return "\n".join(lines)


def ensure(exit_code: int = 2) -> None:
    """不足していれば案内を出して終了する。足りていれば何もしない。"""
    packages = missing()
    if packages:
        sys.stderr.write(explain(packages) + "\n")
        raise SystemExit(exit_code)
