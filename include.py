"""front matter に並べた .md を、変換前の本文に差し込む。

週報のように、同じ中身を週をまたいで使い回したい文書のためのもの。

    取り込み:
      前週: parts/2026-03-09.md
      今週: parts/2026-03-16.md

**見出しは親が持ち、子は中身だけを持つ。** こうすると、今週の .md をそのまま
翌週の前週として使える（子に「前週」「今週」という語が入らないため）。

差し込むのは **Markdown のまま**。HTML にした後で継ぐと、採番や列の組み替えが
文書をまたげず、1 つの .md に書いたときと結果が変わる。
"""
from __future__ import annotations

import os
import posixpath
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from frontmatter import split_front_matter
from rules import keywords
from rules.common import normalize

#: 本文の相対リンク・画像。差し込むときに親から見た位置へ直す。
_LINK_RE = re.compile(r"(?P<prefix>!?\[[^\]]*\]\()(?P<target>[^)\s]+)(?P<suffix>\))")

#: 書き換えない・取り込めないリンク。外部参照とページ内アンカー、絶対パス。
_EXTERNAL_RE = re.compile(r"\A(?:[a-z][a-z0-9+.-]*:|//|#|/)", re.IGNORECASE)

#: 取り込める拡張子。
INCLUDE_EXTS = (".md", ".markdown")

#: 差し込む見出しの深さ（``## 見出し``）。
HEADING_LEVEL = 2


def find_key(meta: Mapping[str, Any]) -> Optional[str]:
    """front matter から取り込みのキーを探す。無ければ None。"""
    words = [normalize(word) for word in keywords.get("include")]
    for key in meta:
        if isinstance(key, str) and normalize(key) in words:
            return key
    return None


def expand(meta: Dict[str, Any], body: str,
           source_path: Optional[Path]) -> Tuple[str, List[str]]:
    """取り込みに並べた .md を ``## 見出し`` として本文の後ろに足す。

    ``(差し込み後の本文, 警告の一覧)`` を返す。読めない参照は見出しだけ残して警告する
    （節が消えると、列の数が変わって組み立てが崩れるため）。
    """
    key = find_key(meta)
    if key is None:
        return body, []

    warnings: List[str] = []
    entries = meta[key]
    if not isinstance(entries, Mapping):
        return body, [
            f"{key}: 「見出し: パス」の並びで書いてください"
            f"（実際: {type(entries).__name__}）"
        ]
    if source_path is None:
        return body, [f"{key}: はファイルから変換したときだけ効きます"]

    source = Path(source_path).resolve()
    parts = [body.rstrip("\n")]
    for heading, target in entries.items():
        parts.append("#" * HEADING_LEVEL + f" {heading}".rstrip())
        text = _read(str(target), source, warnings)
        if text:
            parts.append(text)
    return "\n\n".join(parts) + "\n", warnings


def _read(target: str, source: Path, warnings: List[str]) -> str:
    """参照先を読んで、差し込む本文を返す。読めなければ空を返す。"""
    if not target or _EXTERNAL_RE.match(target):
        warnings.append(f"取り込めるのはリポジトリ内の相対パスだけです: {target}")
        return ""
    if not target.lower().endswith(INCLUDE_EXTS):
        warnings.append(f"取り込めるのは .md だけです: {target}")
        return ""

    path = (source.parent / target).resolve()
    if path == source:
        warnings.append(f"自分自身は取り込めません: {target}")
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="cp932")
        except (OSError, UnicodeDecodeError):
            warnings.append(f"取り込み先を読めません: {target}")
            return ""
    except OSError:
        warnings.append(f"取り込み先が見つかりません: {target}")
        return ""

    # 子の front matter は落とす（単独で変換できるよう、子にも書けるため）。
    _, child_body = split_front_matter(text)
    return _rewrite_links(child_body.strip("\n"), source.parent, path.parent)


def _rewrite_links(text: str, base: Path, child: Path) -> str:
    """子の中の相対パスを、親から見た位置に直す。

    子を別のディレクトリに置けるようにするため。画像や文書間リンクが、
    差し込んだ後もそのまま解決できる。
    """
    if base == child:
        return text

    prefix = Path(os.path.relpath(child, base)).as_posix()

    def fix(match: "re.Match") -> str:
        target = match.group("target")
        if _EXTERNAL_RE.match(target):
            return match.group(0)
        moved = posixpath.normpath(posixpath.join(prefix, target.replace("\\", "/")))
        return f"{match.group('prefix')}{moved}{match.group('suffix')}"

    return _LINK_RE.sub(fix, text)
