"""障害報告 (incident) のルール。"""
from __future__ import annotations

from typing import Any, Dict, List

from rules import derived, keywords, rule
from rules.common import (
    add_class, body_rows, cell_at, classify_status, find_headings, make_badge,
    meta_lookup, normalize, replace_cell_content, table_column_index,
)
from frontmatter import meta_to_text

#: サマリカードに出す項目 (見出し, front matter のキー候補)。
#: 重要度だけは検出語を keywords と共有する (config.yaml で差し替えられるように)。
_SUMMARY_FIELDS = (
    ("発生", ("発生日時", "発生", "検知日時", "occurred")),
    ("復旧", ("復旧日時", "復旧", "解消日時", "recovered")),
    ("影響範囲", ("影響範囲", "影響", "impact")),
    ("重要度", None),
)


@rule("severity_badge")
def severity_badge(soup: Any, meta: Dict[str, Any]) -> None:
    """重要度をバッジ化する（front matter と表の「重要度」列の両方）。"""
    value = meta_lookup(meta, keywords.get("severity"))
    if value is not None:
        text = meta_to_text(value)
        if text:
            derived(meta)["severity"] = {
                "text": text,
                "kind": classify_status(text) or "warn",
            }

    for table in soup.find_all("table"):
        index = table_column_index(table, keywords.get("severity"))
        if index is None:
            continue
        for row in body_rows(table):
            cell = cell_at(row, index)
            if cell is None:
                continue
            text = cell.get_text(strip=True)
            if text:
                replace_cell_content(
                    cell, make_badge(soup, text, classify_status(text) or "warn")
                )


@rule("impact_summary")
def impact_summary(soup: Any, meta: Dict[str, Any]) -> None:
    """front matter から冒頭サマリカード（発生 / 復旧 / 影響範囲 / 重要度）を組み立てる。"""
    cards: List[Dict[str, str]] = []
    for label, keys in _SUMMARY_FIELDS:
        value = meta_lookup(meta, keys or keywords.get("severity"))
        text = meta_to_text(value)
        if not text:
            continue
        kind = classify_status(text) if normalize(label) == normalize("重要度") else None
        cards.append({"label": label, "value": text, "kind": kind or "default"})

    if cards:
        derived(meta)["summary"] = cards


@rule("timeline_table")
def timeline_table(soup: Any, meta: Dict[str, Any]) -> None:
    """時刻列を持つ表をタイムライン表示に変換する。"""
    tables = [t for t in soup.find_all("table") if table_column_index(t, keywords.get("time_column")) is not None]
    if not tables:
        # 列名が無くても「時系列」節の最初の表はタイムラインとして扱う。
        for heading in find_headings(soup, keywords.get("timeline")):
            found = [n for n in heading.find_all_next("table")]
            if found:
                tables = found[:1]
            break

    for table in tables:
        time_index = table_column_index(table, keywords.get("time_column"))
        if time_index is None:
            time_index = 0
        _to_timeline(soup, table, time_index)


def _to_timeline(soup: Any, table: Any, time_index: int) -> None:
    rows = body_rows(table)
    if not rows:
        return

    timeline = soup.new_tag("ol")
    add_class(timeline, "dm-timeline")
    for row in rows:
        cells = row.find_all(["td", "th"])
        item = soup.new_tag("li")
        add_class(item, "dm-timeline__item")

        time_cell = cells[time_index] if time_index < len(cells) else None
        stamp = soup.new_tag("span")
        add_class(stamp, "dm-timeline__time")
        stamp.string = time_cell.get_text(strip=True) if time_cell is not None else ""
        item.append(stamp)

        body = soup.new_tag("div")
        add_class(body, "dm-timeline__body")
        for index, cell in enumerate(cells):
            if index == time_index:
                continue
            block = soup.new_tag("p")
            for child in list(cell.contents):
                block.append(child.extract())
            body.append(block)
        item.append(body)
        timeline.append(item)

    table.replace_with(timeline)
