"""列並べ (columns) のルール。

節を列に並べる種類で使う。並べたときに 1 列が狭くなるため、表を組まずに
「1 行 1 件」で書けるようにするのがねらい。ここにあるのは書式の意味づけだけで、
どんな業務のデータかは問わない。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from rules import rule, warn
from rules.common import (
    HEADING_TAGS, add_class, classify_status, heading_level, make_badge, wrap_section,
)

#: 欄の区切り。全角・半角の縦棒どちらでも書ける。
_SEPARATOR_RE = re.compile(r"[｜|]")

#: 件数の並びの区切り (``残:3 / 新規:1``)。
_COUNT_SEPARATOR_RE = re.compile(r"[/／]")

#: 件数 1 つ分。``ラベル:数値``。
_COUNT_RE = re.compile(r"\A\s*(?P<label>[^:：/／]+?)\s*[:：]\s*(?P<value>\d+)\s*\Z")

#: 件数の並びとみなす最小の個数。1 つだけなら普通の文とみなす。
_MIN_COUNTS = 2

#: 期待する見出し 2 の数。1 つ目が 1 列 (トピックス)、残りが列。
EXPECTED_SECTIONS = 4


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


@rule("group_columns")
def group_columns(soup: Any, meta: Dict[str, Any]) -> None:
    """見出し 2 を「1 つ目 = 1 列」「2 つ目以降 = 列」として組み立てる。

    ``## トピックス / ## 前週 / ## 今週 / ## 来週の予定`` と書いた文書を、
    トピックスは横幅いっぱいの 1 列、残りは列として扱う。
    列の中に小見出し (``### バグ対応``) があれば、小見出しごとにまとめ直し、
    「バグ対応の中に前週・今週・来週の列」という並びにする。
    さらに深い小見出し (``#### 画面まわり``) があれば、その中でもう一段
    まとめ直す（サブ項目ごとに列を並べる）。

    位置で決めるため、見出しの文字列は見ない。``## `` が
    ``EXPECTED_SECTIONS`` 個でないときは警告する（処理は続ける）。
    """
    sections = [tag for tag in soup.find_all("section", recursive=False)
                if "dm-section" in (tag.get("class") or [])]
    if not sections:
        return
    if len(sections) != EXPECTED_SECTIONS:
        warn(meta, f"見出し 2 は {EXPECTED_SECTIONS} 個で書いてください"
                   f"（1 つ目がトピックス、残りが列）。今は {len(sections)} 個です")

    # 1 つ目は列に割り付けず、横幅いっぱいに置く。
    add_class(sections[0], "dm-section--full")

    targets = sections[1:]
    sub_tag, deep_tag = _heading_tags(targets)
    if sub_tag is None or len(targets) < 2:
        # 組み替えるものが無い。残りの節はそのまま列になる。
        return

    column_titles = [_section_title(section) for section in targets]
    order: List[str] = []
    # 小見出し → {列の位置: ノードの並び}
    grouped: Dict[str, Dict[int, List[Any]]] = {}

    for position, section in enumerate(targets):
        for heading, nodes in _split_by_subheading(section, sub_tag):
            name = heading.get_text(strip=True) if heading is not None else ""
            if not name and not _has_content(nodes):
                continue
            if name not in grouped:
                grouped[name] = {}
                order.append(name)
            grouped[name][position] = nodes

    if not order:
        return

    holder = soup.new_tag("div")
    add_class(holder, "dm-groups")
    for name in order:
        holder.append(_make_group(soup, name, grouped[name], column_titles, deep_tag))

    targets[0].insert_before(holder)
    for section in targets:
        section.decompose()


def _heading_tags(sections: List[Any]) -> tuple:
    """節の中で使う見出しを ``(まとまり, サブ項目)`` のタグ名で返す。

    いちばん浅い見出しがまとまりの区切り、その次に浅いものがサブ項目の区切り。
    どちらも無ければ None。
    """
    levels = set()
    for section in sections:
        own = section.find(HEADING_TAGS)
        for heading in section.find_all(HEADING_TAGS):
            if heading is not own:
                levels.add(heading_level(heading))
    ordered = sorted(levels)
    return (
        f"h{ordered[0]}" if ordered else None,
        f"h{ordered[1]}" if len(ordered) > 1 else None,
    )


def _section_title(section: Any) -> str:
    heading = section.find(HEADING_TAGS)
    return heading.get_text(strip=True) if heading is not None else ""


def _split_by_subheading(section: Any, sub_tag: str) -> List[tuple]:
    """節を小見出しで区切り、``(見出しタグ or None, ノードの並び)`` を出現順で返す。

    節は空になる（呼び出し側が組み直す）。小見出しより前にある内容は、
    見出しなしの先頭の組として返す。
    """
    own = section.find(HEADING_TAGS)
    parts: List[tuple] = [(None, [])]
    for node in [child.extract() for child in list(section.contents)]:
        if node is own:
            continue
        if getattr(node, "name", None) == sub_tag:
            parts.append((node, []))
        else:
            parts[-1][1].append(node)
    return parts


def _has_content(nodes: List[Any]) -> bool:
    """空白だけでない中身があるか。"""
    return any(node.get_text(strip=True) if getattr(node, "name", None) else str(node).strip()
               for node in nodes)


def _split_nodes(nodes: List[Any], tag: str) -> List[tuple]:
    """ノードの並びを ``tag`` の見出しで区切る。``_split_by_subheading`` の中身版。"""
    parts: List[tuple] = [(None, [])]
    for node in nodes:
        if getattr(node, "name", None) == tag:
            parts.append((node, []))
        else:
            parts[-1][1].append(node)
    return parts


def _subgroups(columns: Dict[int, List[Any]], deep_tag: Any) -> tuple:
    """まとまりの中身をサブ項目に分け、``(順序, サブ項目名 → {列の位置: ノード})`` を返す。

    サブ項目の見出しより前にある内容 (件数の並びなど) は、名前なしのサブ項目として
    先頭に置く。
    """
    order: List[str] = []
    split: Dict[str, Dict[int, List[Any]]] = {}
    for position, nodes in columns.items():
        parts = _split_nodes(nodes, deep_tag) if deep_tag else [(None, nodes)]
        for heading, part in parts:
            name = heading.get_text(strip=True) if heading is not None else ""
            if not name and not _has_content(part):
                continue
            if name not in split:
                split[name] = {}
                order.append(name)
            split[name][position] = part
    if "" in order:
        # 名前なし (見出しより前の内容) は、どの列で出てきても先頭に置く。
        order.remove("")
        order.insert(0, "")
    return order, split


def _make_group(soup: Any, name: str, columns: Dict[int, List[Any]],
                column_titles: List[str], deep_tag: Any) -> Any:
    group = soup.new_tag("section")
    add_class(group, "dm-group")
    if name:
        title = soup.new_tag("h2")
        add_class(title, "dm-group__title")
        title.string = name
        group.append(title)

    order, split = _subgroups(columns, deep_tag)
    for sub_name in order or [""]:
        group.append(_make_row(soup, sub_name, split.get(sub_name) or {}, column_titles))
    return group


def _make_row(soup: Any, name: str, columns: Dict[int, List[Any]],
              column_titles: List[str]) -> Any:
    row = soup.new_tag("section")
    add_class(row, "dm-subgroup")
    if name:
        title = soup.new_tag("h3")
        add_class(title, "dm-subgroup__title")
        title.string = name
        row.append(title)

    holder = soup.new_tag("div")
    add_class(holder, "dm-group__columns")
    for position, column_title in enumerate(column_titles):
        # 中身が無い列も枠だけ残す。列の位置が節ごとにずれないようにするため。
        holder.append(_make_column(soup, column_title, columns.get(position) or []))
    row.append(holder)
    return row


def _make_column(soup: Any, title: str, nodes: List[Any]) -> Any:
    column = soup.new_tag("section")
    add_class(column, "dm-column")
    label = soup.new_tag("p")
    add_class(label, "dm-column__title")
    label.string = title
    column.append(label)

    if not _has_content(nodes):
        add_class(column, "dm-column--empty")
        empty = soup.new_tag("p")
        add_class(empty, "dm-column__empty")
        empty.string = "—"
        column.append(empty)
        return column

    for node in nodes:
        column.append(node)
    return column


@rule("topic_cards")
def topic_cards(soup: Any, meta: Dict[str, Any]) -> None:
    """1 列にした節を、小見出しごとの枠に分ける。

    ``group_columns`` が 1 列にした節（1 つ目の見出し 2）が対象。
    ``### 見出し`` から次の ``###`` までが 1 枠になり、枠の中は複数行でも書ける。
    小見出しより前に書いた内容は、枠の外に残す。
    """
    for section in soup.find_all("section"):
        if "dm-section--full" not in (section.get("class") or []):
            continue
        own = section.find(HEADING_TAGS)
        headings = [tag for tag in section.find_all(HEADING_TAGS)
                    if tag is not own and tag.parent is section]
        if not headings:
            continue

        holder = soup.new_tag("div")
        add_class(holder, "dm-topics")
        headings[0].insert_before(holder)
        for heading in headings:
            holder.append(wrap_section(soup, heading, "dm-topic"))
