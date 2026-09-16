"""列並べ (columns) のルール。

節を列に並べる種類で使う。並べたときに 1 列が狭くなるため、表を組まずに
「1 行 1 件」で書けるようにするのがねらい。ここにあるのは書式の意味づけだけで、
どんな業務のデータかは問わない。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from rules import rule
from rules.common import add_class, classify_status, make_badge

#: 欄の区切り。全角・半角の縦棒どちらでも書ける。
_SEPARATOR_RE = re.compile(r"[｜|]")

#: 件数の並びの区切り (``残:3 / 新規:1``)。
_COUNT_SEPARATOR_RE = re.compile(r"[/／]")

#: 件数 1 つ分。``ラベル:数値``。
_COUNT_RE = re.compile(r"\A\s*(?P<label>[^:：/／]+?)\s*[:：]\s*(?P<value>\d+)\s*\Z")

#: 件数の並びとみなす最小の個数。1 つだけなら普通の文とみなす。
_MIN_COUNTS = 2


@rule("entry_card")
def entry_card(soup: Any, meta: Dict[str, Any]) -> None:
    """``｜`` で区切ったリスト項目を、見出し・属性・説明のカードにする。

    欄は ``見出し｜属性…｜説明`` の順に読む。属性のうち状態を表す語はバッジになる。
    説明を付けない場合は末尾の欄を空にする（``見出し｜属性｜``）。
    """
    for list_tag in soup.find_all(["ul", "ol"]):
        items = [item for item in list_tag.find_all("li", recursive=False)
                 if _is_entry(item)]
        if not items:
            continue
        add_class(list_tag, "dm-entries")
        for item in items:
            _build_entry(soup, item)


@rule("count_summary")
def count_summary(soup: Any, meta: Dict[str, Any]) -> None:
    """``残:3 / 新規:1 / 完了:2`` だけの段落を、件数の並びにする。"""
    for paragraph in list(soup.find_all("p")):
        # 装飾やリンクが入っている段落は書き手の意図が読めないため触らない。
        if paragraph.find(True) is not None:
            continue
        counts = _parse_counts(paragraph.get_text())
        if not counts:
            continue
        paragraph.replace_with(_make_counts(soup, counts))


def _is_entry(item: Any) -> bool:
    """カードにするリスト項目か (区切りが 1 つ以上あり、入れ子のリストを持たない)。"""
    if item.find(["ul", "ol"]) is not None:
        return False
    return bool(_SEPARATOR_RE.search(item.get_text()))


def _build_entry(soup: Any, item: Any) -> None:
    fields = _split_fields(item)
    add_class(item, "dm-entry")

    head = soup.new_tag("p")
    add_class(head, "dm-entry__head")
    key = soup.new_tag("span")
    add_class(key, "dm-entry__key")
    _fill(key, fields[0])
    head.append(key)

    for nodes in fields[1:-1]:
        text = _field_text(nodes)
        if not text:
            continue
        kind = classify_status(text)
        if kind:
            head.append(make_badge(soup, text, kind))
            continue
        attribute = soup.new_tag("span")
        add_class(attribute, "dm-entry__meta")
        _fill(attribute, nodes)
        head.append(attribute)

    item.append(head)

    body_nodes = fields[-1] if len(fields) > 1 else []
    if _field_text(body_nodes):
        body = soup.new_tag("p")
        add_class(body, "dm-entry__body")
        _fill(body, body_nodes)
        item.append(body)


def _split_fields(item: Any) -> List[List[Any]]:
    """``<li>`` の中身を区切りで分け、欄ごとの「ノードの並び」として返す。

    文字列だけを区切るため、欄の中のリンクや強調はそのまま残る。
    項目は空になる (呼び出し側が組み直す)。
    """
    fields: List[List[Any]] = [[]]
    for child in [node.extract() for node in list(item.contents)]:
        if getattr(child, "name", None) is not None:
            fields[-1].append(child)
            continue
        parts = _SEPARATOR_RE.split(str(child))
        fields[-1].append(parts[0])
        for part in parts[1:]:
            fields.append([part])
    return fields


def _field_text(nodes: List[Any]) -> str:
    return "".join(node if isinstance(node, str) else node.get_text()
                   for node in nodes).strip()


def _fill(target: Any, nodes: List[Any]) -> None:
    """欄のノードを ``target`` に移す (前後の空白は落とす)。"""
    pieces = list(nodes)
    if pieces and isinstance(pieces[0], str):
        pieces[0] = pieces[0].lstrip()
    if pieces and isinstance(pieces[-1], str):
        pieces[-1] = pieces[-1].rstrip()
    for node in pieces:
        if isinstance(node, str) and not node:
            continue
        target.append(node)


def _parse_counts(text: str) -> List[tuple]:
    """``残:3 / 新規:1`` を ``[("残", "3"), ("新規", "1")]`` にする。

    1 つでも形が崩れていれば、普通の文とみなして空を返す。
    """
    counts = []
    for part in _COUNT_SEPARATOR_RE.split(text):
        match = _COUNT_RE.match(part)
        if not match:
            return []
        counts.append((match.group("label"), match.group("value")))
    return counts if len(counts) >= _MIN_COUNTS else []


def _make_counts(soup: Any, counts: List[tuple]) -> Any:
    holder = soup.new_tag("ul")
    add_class(holder, "dm-counts")
    for label, value in counts:
        item = soup.new_tag("li")
        add_class(item, "dm-count")
        name = soup.new_tag("span")
        add_class(name, "dm-count__label")
        name.string = label
        number = soup.new_tag("span")
        add_class(number, "dm-count__value")
        number.string = value
        item.append(name)
        item.append(number)
        holder.append(item)
    return holder
