"""YAML front matter の分離。

``.md`` 先頭の ``---`` 〜 ``---`` を front matter として取り出す。
種類の判定はここでは行わず、``type`` の解釈は converter 側に任せる。
"""
from __future__ import annotations

import re
from typing import Any, Dict, Tuple

try:
    import yaml
except ImportError as e:  # pragma: no cover - 依存が無い環境向けの案内
    raise ImportError("PyYAML is required. Install with: pip install pyyaml") from e

# 終端は `---` と `...`（YAML のドキュメント終端）の両方を許容する。
# 先頭の BOM は Windows で作られた .md でよく混ざるため読み飛ばす。
_FRONT_MATTER_RE = re.compile(
    r"\A﻿?---[ \t]*\r?\n(?P<meta>.*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)",
    re.DOTALL,
)


class FrontMatterError(ValueError):
    """front matter が YAML として解釈できないときに送出。"""


def split_front_matter(text: str) -> Tuple[Dict[str, Any], str]:
    """``(meta, body)`` に分割する。front matter が無ければ ``({}, text)``。"""
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text.lstrip("﻿")

    try:
        meta = yaml.safe_load(match.group("meta"))
    except yaml.YAMLError as e:
        raise FrontMatterError(f"front matter の YAML を解釈できません: {e}") from e

    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise FrontMatterError(
            f"front matter はマッピングである必要があります (実際: {type(meta).__name__})"
        )

    return {str(k): v for k, v in meta.items()}, text[match.end():]


def meta_to_text(value: Any) -> str:
    """front matter の値を表示用の 1 行に整える。

    リストは ``, `` 区切り、日付は ISO 形式 (PyYAML が date に変換するため)。
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "はい" if value else "いいえ"
    if isinstance(value, (list, tuple)):
        return ", ".join(meta_to_text(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{k}: {meta_to_text(v)}" for k, v in value.items())
    return str(value)
