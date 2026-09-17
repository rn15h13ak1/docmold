"""箇条書きを表にするルール。

``| --- |`` の桁合わせを書かずに済ませるためのもの。列を増やしたり値を直したりする
のに行をまたいだ編集が要らず、1 セル = 1 行で直せる。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from rules import keywords, rule, warn
from rules.common import add_class, normalize

#: 列の区切り。全角・半角の縦棒どちらでも書ける。
_COLUMN_SEPARATOR_RE = re.compile(r"[｜|]")

#: 目印の行 (``表: 作業｜担当｜状態``)。
_MARKER_RE = re.compile(r"\A\s*(?P<word>[^:：]+?)\s*[:：]\s*(?P<columns>.+)\Z")

#: 子の行の「列名: 値」。
_LABEL_RE = re.compile(r"\A\s*(?P<label>[^:：]{1,20})\s*[:：]\s*(?P<rest>.*)\Z", re.S)

#: その列を空欄にする書き方。
_EMPTY_MARKS = frozenset({"-", "ー", "―", "—", "‐", "−"})


@rule("list_table")
def list_table(soup: Any, meta: Dict[str, Any]) -> None:
    """``表: 列名｜列名`` の行に続く箇条書きを表にする。

    親の行が 1 列目、字下げした子の行が 2 列目以降。子の行は書いた順に列へ入り、
    ``状態: 未着手`` のように列名を書いた行だけはその列に入る。``-`` だけの行は空欄。
    列の数が合わない行は警告する（処理は続く）。

    目印の行が無い箇条書きには何もしない。
    """
    for paragraph in list(soup.find_all("p")):
        columns = _marker_columns(paragraph)
        if columns is None:
            continue
        target = _next_element(paragraph)
        if target is None or target.name != "ul":
            continue

        table = _build_table(soup, columns, target, meta)
        target.replace_with(table)
        paragraph.decompose()


def _marker_columns(paragraph: Any) -> Optional[List[str]]:
    """目印の行なら列名の並びを返す。そうでなければ None。"""
    if paragraph.find(True) is not None:
        # 装飾やリンクが入っている段落は、書き手の意図が読めないため触らない。
        return None
    match = _MARKER_RE.match(paragraph.get_text())
    if not match:
        return None
    words = [normalize(word) for word in keywords.get("table_marker")]
    if normalize(match.group("word")) not in words:
        return None
    columns = [part.strip() for part in _COLUMN_SEPARATOR_RE.split(match.group("columns"))]
    return columns if len(columns) >= 2 else None


def _next_element(tag: Any) -> Any:
    for sibling in tag.next_siblings:
        if getattr(sibling, "name", None) is not None:
            return sibling
        if str(sibling).strip():
            return None
    return None


def _build_table(soup: Any, columns: List[str], source: Any, meta: Dict[str, Any]) -> Any:
    table = soup.new_tag("table")
    add_class(table, "dm-table")

    head = soup.new_tag("thead")
    head_row = soup.new_tag("tr")
    for name in columns:
        cell = soup.new_tag("th")
        cell.string = name
        head_row.append(cell)
    head.append(head_row)
    table.append(head)

    body = soup.new_tag("tbody")
    for number, item in enumerate(source.find_all("li", recursive=False), 1):
        body.append(_build_row(soup, columns, item, meta, number))
    table.append(body)
    return table


def _build_row(soup: Any, columns: List[str], item: Any,
               meta: Dict[str, Any], number: int) -> Any:
    values: List[Optional[List[Any]]] = [None] * len(columns)
    values[0] = _head_nodes(item)

    children = _child_items(item)
    named = False
    cursor = 1
    for child in children:
        nodes = [node.extract() for node in list(child.contents)]
        index, rest = _split_label(nodes, columns)
        if index is None:
            while cursor < len(columns) and values[cursor] is not None:
                cursor += 1
            index, rest = cursor, nodes
            cursor += 1
        else:
            named = True

        if index >= len(columns):
            warn(meta, _where(columns, number)
                 + f"は {len(columns)} 列のところ {len(children) + 1} 個ありました")
            break
        values[index] = [] if _is_empty_mark(rest) else rest

    # 列名を書いていない行が短い場合は数え間違いの可能性が高い。
    if not named and len(children) + 1 < len(columns):
        warn(meta, _where(columns, number)
             + f"は {len(columns)} 列のところ {len(children) + 1} 個でした")

    row = soup.new_tag("tr")
    for nodes in values:
        cell = soup.new_tag("td")
        for node in nodes or []:
            cell.append(node)
        row.append(cell)
    return row


def _where(columns: List[str], number: int) -> str:
    return f"表「{columns[0]}」の {number} 行目"


def _head_nodes(item: Any) -> List[Any]:
    """項目の 1 行目 (入れ子のリストより前) のノードを取り出す。"""
    nodes = []
    for child in list(item.contents):
        name = getattr(child, "name", None)
        if name in ("ul", "ol"):
            break
        if name == "p" and not nodes:
            nodes = [node.extract() for node in list(child.contents)]
            continue
        nodes.append(child.extract())
    return nodes


def _child_items(item: Any) -> List[Any]:
    """字下げして書いた子の行を返す。"""
    nested = item.find(["ul", "ol"])
    return nested.find_all("li", recursive=False) if nested is not None else []


def _split_label(nodes: List[Any], columns: List[str]) -> Tuple[Optional[int], List[Any]]:
    """先頭の「列名: 」を切り出して ``(列の位置, 残りのノード)`` を返す。

    列名に一致しないものは値の一部とみなす (``期限: 3/20`` のような書き方を
    そのまま通すため)。
    """
    if not nodes or getattr(nodes[0], "name", None) is not None:
        return None, nodes
    match = _LABEL_RE.match(str(nodes[0]))
    if not match:
        return None, nodes
    label = normalize(match.group("label"))
    for index, name in enumerate(columns):
        if index and normalize(name) == label:
            return index, [match.group("rest")] + list(nodes[1:])
    return None, nodes


def _is_empty_mark(nodes: List[Any]) -> bool:
    text = "".join(node if isinstance(node, str) else node.get_text()
                   for node in nodes).strip()
    return text in _EMPTY_MARKS
