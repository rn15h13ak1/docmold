"""ルールが共有するヘルパ。

ここにルールの登録は無い。DOM 操作の定型 (見出しで節を切り出す / バッジを作る /
表の列を名前で引く) をまとめ、各ルールを数十行に収めるためのモジュール。
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence

from rules import keywords

HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")

#: バッジの種類 (CSS クラス ``dm-badge--<kind>``) → 検出語のグループ名。
#: 語そのものは rules/keywords.py にあり、config.yaml から差し替えられる。
STATUS_GROUPS = (("ok", "status_ok"), ("warn", "status_warn"), ("danger", "status_danger"))

_PERCENT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")


def normalize(text: Optional[str]) -> str:
    """比較用に正規化する (全角→半角、小文字化、空白除去)。"""
    if not text:
        return ""
    return unicodedata.normalize("NFKC", text).strip().lower().replace(" ", "")


def heading_level(tag: Any) -> int:
    """``h2`` → 2。見出しでなければ 0。"""
    name = getattr(tag, "name", "") or ""
    return int(name[1]) if name in HEADING_TAGS else 0


def find_headings(soup: Any, keywords: Sequence[str]) -> List[Any]:
    """見出し文字列に ``keywords`` のいずれかを含む見出しを、出現順で返す。"""
    targets = [normalize(k) for k in keywords]
    return [
        tag for tag in soup.find_all(HEADING_TAGS)
        if any(key in normalize(tag.get_text()) for key in targets)
    ]


def section_nodes(heading: Any) -> List[Any]:
    """見出しに属するノード (次の同レベル以上の見出しまで) を返す。見出し自身は含まない。"""
    level = heading_level(heading)
    nodes = []
    for sibling in heading.next_siblings:
        if heading_level(sibling) and heading_level(sibling) <= level:
            break
        nodes.append(sibling)
    return nodes


def find_in_section(heading: Any, names: Sequence[str]) -> List[Any]:
    """節の中から ``names`` のタグを取り出す (節自身が該当する場合も含む)。"""
    found = []
    for node in section_nodes(heading):
        if getattr(node, "name", None) is None:
            continue
        if node.name in names:
            found.append(node)
        found.extend(node.find_all(names))
    return found


def add_class(tag: Any, *classes: str) -> None:
    """タグに CSS クラスを追加する (重複は付けない)。"""
    current = tag.get("class", [])
    if isinstance(current, str):
        current = current.split()
    for cls in classes:
        if cls not in current:
            current.append(cls)
    tag["class"] = current


def classify_status(text: str) -> Optional[str]:
    """状態文字列からバッジの種類を判定する。該当なしは None。

    完全一致を先に見る。「未着手」が warn の「中」を含むように、部分一致だけだと
    取り違えるため。
    """
    value = normalize(text)
    if not value:
        return None

    groups = [(kind, keywords.get(group)) for kind, group in STATUS_GROUPS]
    for kind, words in groups:
        if any(normalize(word) == value for word in words):
            return kind
    for kind, words in groups:
        if any(normalize(word) in value for word in words):
            return kind
    return None


def make_badge(soup: Any, text: str, kind: str = "default") -> Any:
    """``<span class="dm-badge dm-badge--kind">text</span>`` を作る。"""
    badge = soup.new_tag("span")
    add_class(badge, "dm-badge", f"dm-badge--{kind}")
    badge.string = text
    return badge


def make_callout(soup: Any, kind: str, title: str) -> Any:
    """タイトル付きのコールアウト ``<div>`` を作る (中身は呼び出し側で入れる)。"""
    box = soup.new_tag("div")
    add_class(box, "dm-callout", f"dm-callout--{kind}")
    if title:
        head = soup.new_tag("p")
        add_class(head, "dm-callout__title")
        head.string = title
        box.append(head)
    return box


def wrap_section(soup: Any, heading: Any, *classes: str) -> Any:
    """見出しとその節を ``<section>`` で包み、包んだ要素を返す。"""
    nodes = section_nodes(heading)
    wrapper = soup.new_tag("section")
    add_class(wrapper, *classes)
    heading.insert_before(wrapper)
    wrapper.append(heading.extract())
    for node in nodes:
        wrapper.append(node.extract())
    return wrapper


def table_column_index(table: Any, keywords: Sequence[str]) -> Optional[int]:
    """ヘッダ行に ``keywords`` を含む列の 0 始まりの位置を返す。無ければ None。"""
    header = table.find("tr")
    if header is None:
        return None
    cells = header.find_all(["th", "td"])
    targets = [normalize(k) for k in keywords]
    for index, cell in enumerate(cells):
        label = normalize(cell.get_text())
        if any(key in label for key in targets):
            return index
    return None


def body_rows(table: Any) -> List[Any]:
    """ヘッダ行を除いたデータ行を返す。"""
    rows = table.find_all("tr")
    return [row for row in rows if row.find("td") is not None]


def cell_at(row: Any, index: Optional[int]) -> Optional[Any]:
    if index is None:
        return None
    cells = row.find_all(["td", "th"])
    return cells[index] if index < len(cells) else None


def replace_cell_content(cell: Any, node: Any) -> None:
    """セルの中身を ``node`` 1 つで置き換える。"""
    cell.clear()
    cell.append(node)


def parse_percent(text: str) -> Optional[float]:
    """``80%`` / ``80 %`` から 0〜100 の数値を取り出す。"""
    match = _PERCENT_RE.search(unicodedata.normalize("NFKC", text or ""))
    if not match:
        return None
    return max(0.0, min(100.0, float(match.group(1))))


def meta_lookup(meta: Dict[str, Any], keywords: Iterable[str]) -> Optional[Any]:
    """front matter から、キー名に ``keywords`` を含む最初の値を返す。"""
    targets = [normalize(k) for k in keywords]
    for key, value in meta.items():
        if key.startswith("_"):
            continue
        name = normalize(key)
        if any(target in name or name in target for target in targets):
            return value
    return None
