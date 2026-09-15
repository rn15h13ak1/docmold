"""議事録 (minutes) のルール。"""
from __future__ import annotations

import re
from typing import Any, Dict

from rules import keywords, rule
from rules.common import (
    add_class, body_rows, cell_at, find_headings, find_in_section, make_badge,
    make_callout, section_nodes, table_column_index, replace_cell_content,
)

# 「担当: 山田」「担当者：山田」「@山田」を担当者として拾う。
_OWNER_RE = re.compile(r"(?:担当者?\s*[:：]\s*|@)\s*([^\s、,（(/]+)")
# 行頭の GFM 風チェックボックス記法。python-markdown は解釈しないためここで処理する。
_TASK_MARK_RE = re.compile(r"^\s*\[([ xX])\]\s*")


@rule("attendee_table")
def attendee_table(soup: Any, meta: Dict[str, Any]) -> None:
    """「出席者」節の氏名をバッジ化する（リスト・表のどちらでも）。"""
    for heading in find_headings(soup, keywords.get("attendee")):
        for ul in find_in_section(heading, ["ul", "ol"]):
            add_class(ul, "dm-attendees")
            for li in ul.find_all("li", recursive=False):
                add_class(li, "dm-attendee")
        for table in find_in_section(heading, ["table"]):
            add_class(table, "dm-table", "dm-table--attendees")
            index = table_column_index(table, ["氏名", "名前", *keywords.get("attendee")])
            for row in body_rows(table):
                cell = cell_at(row, index)
                if cell is not None and cell.get_text(strip=True):
                    replace_cell_content(cell, make_badge(soup, cell.get_text(strip=True), "person"))


@rule("todo_checklist")
def todo_checklist(soup: Any, meta: Dict[str, Any]) -> None:
    """「ToDo」節のリストをチェックボックス化し、担当者をバッジにする。"""
    for heading in find_headings(soup, keywords.get("todo")):
        for ul in find_in_section(heading, ["ul", "ol"]):
            add_class(ul, "dm-checklist")
            for li in ul.find_all("li"):
                _make_checkbox_item(soup, li)

    # 明示的な [ ] / [x] は書き手の意図が曖昧でないため、節の外でも処理する。
    for li in soup.find_all("li"):
        if _TASK_MARK_RE.match(li.get_text()):
            _make_checkbox_item(soup, li)
            parent = li.find_parent(["ul", "ol"])
            if parent is not None:
                add_class(parent, "dm-checklist")


@rule("decision_highlight")
def decision_highlight(soup: Any, meta: Dict[str, Any]) -> None:
    """「決定事項」節をコールアウトで囲んで目立たせる。"""
    for heading in find_headings(soup, keywords.get("decision")):
        nodes = section_nodes(heading)
        if not nodes:
            continue
        box = make_callout(soup, "decision", "")
        heading.insert_after(box)
        for node in nodes:
            box.append(node.extract())


def _make_checkbox_item(soup: Any, li: Any) -> None:
    """``<li>`` の先頭に無効化済みチェックボックスを差し込む。"""
    if li.find("input", class_="dm-check") is not None:
        return

    checked = False
    for text_node in li.find_all(string=True):
        match = _TASK_MARK_RE.match(text_node)
        if match:
            checked = match.group(1).lower() == "x"
            text_node.replace_with(text_node[match.end():])
            break

    box = soup.new_tag("input", attrs={"type": "checkbox"})
    add_class(box, "dm-check")
    # 配布物として配る HTML なので、状態は Markdown 側の記述で固定する。
    box["disabled"] = "disabled"
    if checked:
        box["checked"] = "checked"
        add_class(li, "dm-checklist__item--done")
    add_class(li, "dm-checklist__item")
    li.insert(0, box)

    _badge_owner(soup, li)


def _badge_owner(soup: Any, li: Any) -> None:
    """「担当: 山田」「@山田」を担当者バッジに置き換える。"""
    for text_node in list(li.find_all(string=True)):
        if text_node.find_parent("span", class_="dm-badge") is not None:
            continue
        text = str(text_node)
        match = _OWNER_RE.search(text)
        if not match:
            continue
        badge = make_badge(soup, match.group(1), "person")
        pieces = [text[:match.start()], badge, text[match.end():]]
        text_node.replace_with(*[piece for piece in pieces if not isinstance(piece, str) or piece])
        return
