"""引用の記法で書かれたコールアウトのルール。

``> [!warning] 見出し`` で始まる引用を、枠付きのコールアウトに変える。
Obsidian 固有の記法ではなく、GitHub（NOTE / TIP / IMPORTANT / WARNING / CAUTION）
などでも使われる引用の慣用のため、種類を問わず使えるルールとして置く。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from rules import rule
from rules.common import add_class, make_callout

#: 段落の先頭にある ``[!種別]``。後ろの ``-`` / ``+`` は折りたたみの指定。
_MARKER_RE = re.compile(r"^\s*\[!(?P<kind>[^\]\s]+)\](?P<fold>[-+]?)[ \t]*(?P<title>.*)$")

#: 種別 → 見た目の系統。ここに無い種別は既定（info）で通す。
#: Obsidian もその派生も語彙を増やし続けるため、既知の語だけを通すと利用側が追随できない。
_KINDS = {
    "tip": "ok", "success": "ok", "check": "ok", "done": "ok",
    "warning": "warn", "important": "warn", "caution": "warn", "attention": "warn",
    "danger": "danger", "error": "danger", "bug": "danger", "failure": "danger",
    "fail": "danger", "missing": "danger",
}
_DEFAULT_KIND = "info"


@rule("callout_blockquote")
def callout_blockquote(soup: Any, meta: Dict[str, Any]) -> None:
    """``> [!warning] 見出し`` で始まる引用を、枠付きのコールアウトにする。

    ``[!note]-`` は閉じた折りたたみ、``[!note]+`` は開いた折りたたみになる。
    """
    # 入れ子の内側から処理する。外側を組み替えたあとで内側を探すと、
    # 付け替えた要素を見失うため。
    for quote in reversed(soup.find_all("blockquote")):
        _split_into_callouts(soup, quote)


def _split_into_callouts(soup: Any, quote: Any) -> None:
    """1 つの引用を、目印ごとに区切ってコールアウトに置き換える。

    Python-Markdown は、空行だけで隔てられた連続する引用を 1 つの ``<blockquote>``
    にまとめる。``> [!info]`` と ``> [!tip]`` を続けて書くと同じ引用に入るため、
    先頭だけを見ると 2 つ目以降が地の文として残る。段落ごとに目印を探して切る。

    このため、コールアウトの直後に空行を挟んで書いた**普通の引用**は、区別が付かず
    コールアウトの中に入る（結合は DOM になる前に済んでおり、境目が残らない）。
    """
    segments = _segments(list(quote.children))
    if not any(marker for marker, _ in segments):
        return

    for marker, nodes in segments:
        if marker is None:
            # 目印より前の中身は、引用のまま残す。
            box = soup.new_tag("blockquote")
        else:
            box = _make_box(soup, *marker)
        for node in nodes:
            box.append(node.extract())
        quote.insert_before(box)

    quote.decompose()


def _segments(children: List[Any]) -> List[Tuple[Optional[Tuple[str, str, str]], List[Any]]]:
    """引用の中身を ``(目印, その区間の要素)`` の並びに切り分ける。

    目印より前に中身があれば、先頭だけ目印なしの区間になる。
    """
    segments: List[Tuple[Optional[Tuple[str, str, str]], List[Any]]] = []
    for node in children:
        if getattr(node, "name", None) is None and not str(node).strip():
            continue  # 要素の間の改行
        marker = _take_marker(node)
        if marker is not None or not segments:
            segments.append((marker, []))
        segments[-1][1].append(node)
    return segments


def _take_marker(node: Any) -> Optional[Tuple[str, str, str]]:
    """段落の先頭が目印なら ``(系統, 折りたたみ, タイトル)`` を返し、目印を取り除く。

    ``> [!warning] 見出し`` の次の行に本文を続けると、Markdown は両方を 1 つの段落に
    入れる（``見出し\\n本文`` という 1 つの文字列になる）。目印の行だけを切り出し、
    残りは本文として段落に戻す。
    """
    if getattr(node, "name", None) != "p":
        return None
    first = node.find(string=True)
    if first is None:
        return None

    head, separator, rest = str(first).partition("\n")
    match = _MARKER_RE.match(head)
    if not match:
        return None

    title = match.group("title").strip()
    first.replace_with(rest if separator else "")
    if not node.get_text().strip() and not node.find(["img", "br"]):
        node.decompose()  # 目印だけの段落は残さない
    return (_KINDS.get(match.group("kind").lower(), _DEFAULT_KIND),
            match.group("fold"), title)


def _make_box(soup: Any, kind: str, fold: str, title: str) -> Any:
    """コールアウトの外枠を作る。折りたたみの指定があれば ``<details>`` にする。"""
    if not fold:
        return make_callout(soup, kind, title)

    box = soup.new_tag("details")
    add_class(box, "dm-callout", f"dm-callout--{kind}")
    if fold == "+":
        box["open"] = "open"
    summary = soup.new_tag("summary")
    add_class(summary, "dm-callout__title")
    summary.string = title or "詳細"
    box.append(summary)
    return box
