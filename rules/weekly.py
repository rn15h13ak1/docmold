"""週次報告 (weekly) のルール。"""
from __future__ import annotations

from typing import Any, Dict

from rules import rule
from rules.common import (
    add_class, body_rows, cell_at, classify_status, make_badge, parse_percent,
    replace_cell_content, table_column_index,
)

_STATUS_COLUMNS = ("状態", "ステータス", "status", "進行", "対応状況")
_PROGRESS_COLUMNS = ("進捗", "進捗率", "達成率", "progress", "完了率")


@rule("status_badge")
def status_badge(soup: Any, meta: Dict[str, Any]) -> None:
    """表の「状態」列をバッジ化する。"""
    for table in soup.find_all("table"):
        index = table_column_index(table, _STATUS_COLUMNS)
        if index is None:
            continue
        add_class(table, "dm-table")
        for row in body_rows(table):
            cell = cell_at(row, index)
            if cell is None:
                continue
            text = cell.get_text(strip=True)
            if text:
                replace_cell_content(cell, make_badge(soup, text, classify_status(text) or "default"))


@rule("progress_bar")
def progress_bar(soup: Any, meta: Dict[str, Any]) -> None:
    """表の「進捗」列の ``80%`` を進捗バーにする。"""
    for table in soup.find_all("table"):
        index = table_column_index(table, _PROGRESS_COLUMNS)
        if index is None:
            continue
        add_class(table, "dm-table")
        for row in body_rows(table):
            cell = cell_at(row, index)
            if cell is None:
                continue
            percent = parse_percent(cell.get_text())
            if percent is None:
                continue
            replace_cell_content(cell, _make_bar(soup, percent))


def _make_bar(soup: Any, percent: float) -> Any:
    text = f"{percent:g}%"
    wrapper = soup.new_tag("span")
    add_class(wrapper, "dm-progress")
    # 印刷時やスタイルが効かない環境でも読めるよう、数値をテキストでも持たせる。
    wrapper["title"] = text

    track = soup.new_tag("span")
    add_class(track, "dm-progress__track")
    fill = soup.new_tag("span")
    add_class(fill, "dm-progress__fill")
    fill["style"] = f"width: {percent:g}%;"
    track.append(fill)
    wrapper.append(track)

    label = soup.new_tag("span")
    add_class(label, "dm-progress__label")
    label.string = text
    wrapper.append(label)
    return wrapper
