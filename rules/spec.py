"""設計書 (spec) のルール。図表の自動採番と相互参照。"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from rules import derived, rule
from rules.common import add_class

# 本文中の「図 3」「表 12」。採番済みの図表があるときだけリンクにする。
_REFERENCE_RE = re.compile(r"(図|表)\s*(\d+)")
# 表のキャプションとして扱う段落 (「表: …」「表 1: …」)。
_TABLE_CAPTION_RE = re.compile(r"^\s*表\s*\d*\s*[:：]\s*(?P<text>.+)$")
_FIGURE_CAPTION_RE = re.compile(r"^\s*図\s*\d*\s*[:：]\s*(?P<text>.+)$")


@rule("figure_caption")
def figure_caption(soup: Any, meta: Dict[str, Any]) -> None:
    """画像と Mermaid の図を ``<figure>`` にして「図 N: 説明」を自動採番する。

    説明は画像なら ``alt``、Mermaid なら直前の「図: …」の段落から取る
    （表のキャプションと同じ書き方に揃えている）。
    """
    figures: List[Dict[str, str]] = []

    for node in soup.find_all(["img", "pre"]):
        if node.name == "pre" and not _is_diagram(node):
            continue
        if node.find_parent("figure") is not None:
            continue

        number = len(figures) + 1
        anchor = f"fig-{number}"
        figure = soup.new_tag("figure")
        add_class(figure, "dm-figure")
        figure["id"] = anchor

        if node.name == "img":
            caption_text = _place_image(figure, node)
        else:
            caption_text = _place_diagram(figure, node)

        caption = soup.new_tag("figcaption")
        add_class(caption, "dm-figure__caption")
        caption.string = f"図 {number}" + (f": {caption_text}" if caption_text else "")
        figure.append(caption)
        figures.append({"number": str(number), "anchor": anchor, "text": caption_text})

    if figures:
        derived(meta)["figures"] = figures


def _is_diagram(tag: Any) -> bool:
    """Mermaid の図か（``mermaid_ext`` が付けたクラスで見分ける）。"""
    return "mermaid" in (tag.get("class") or [])


def _place_image(figure: Any, image: Any) -> str:
    """画像を figure の中に移し、説明文を返す。"""
    # 画像だけの段落は figure に置き換える（段落の入れ子を残さない）。
    paragraph = image.find_parent("p")
    host = paragraph if paragraph is not None and _only_child(paragraph, image) else image
    host.insert_before(figure)
    figure.append(image.extract())

    if host is not image:
        caption_text = _caption_from(host, _FIGURE_CAPTION_RE) or image.get("alt", "")
        host.decompose()
        return caption_text
    return image.get("alt", "")


def _place_diagram(figure: Any, diagram: Any) -> str:
    """Mermaid の図を figure の中に移し、説明文を返す。

    説明は直前の「図: …」の段落から取り、その段落は取り除く。
    """
    caption_text = ""
    previous = _previous_element(diagram)
    if previous is not None and previous.name == "p":
        found = _caption_from(previous, _FIGURE_CAPTION_RE)
        if found:
            caption_text = found
            previous.decompose()

    diagram.insert_before(figure)
    figure.append(diagram.extract())
    return caption_text


@rule("table_caption")
def table_caption(soup: Any, meta: Dict[str, Any]) -> None:
    """表に「表 N: 説明」のキャプションを付けて自動採番する。"""
    tables: List[Dict[str, str]] = []
    for table in soup.find_all("table"):
        number = len(tables) + 1
        anchor = f"tbl-{number}"
        table["id"] = table.get("id") or anchor
        add_class(table, "dm-table")

        text = ""
        previous = _previous_element(table)
        if previous is not None and previous.name == "p":
            found = _caption_from(previous, _TABLE_CAPTION_RE)
            if found:
                text = found
                previous.decompose()

        caption = table.find("caption")
        if caption is None:
            caption = soup.new_tag("caption")
            table.insert(0, caption)
        add_class(caption, "dm-table__caption")
        caption.string = f"表 {number}" + (f": {text}" if text else "")
        tables.append({"number": str(number), "anchor": anchor, "text": text})

    if tables:
        derived(meta)["tables"] = tables


@rule("cross_reference")
def cross_reference(soup: Any, meta: Dict[str, Any]) -> None:
    """本文中の「図 N」「表 N」を、採番済みの図表へのリンクにする。

    ``figure_caption`` / ``table_caption`` より後に適用すること
    （採番が済んでいない番号はリンクにしない）。
    """
    store = derived(meta)
    numbers = {
        "図": {item["number"] for item in store.get("figures", [])},
        "表": {item["number"] for item in store.get("tables", [])},
    }
    if not (numbers["図"] or numbers["表"]):
        return

    prefixes = {"図": "fig", "表": "tbl"}
    skip_parents = ("figcaption", "caption", "a", "code", "pre", "h1", "h2", "h3")

    for text_node in list(soup.find_all(string=_REFERENCE_RE.search)):
        if text_node.find_parent(skip_parents) is not None:
            continue

        pieces: List[Any] = []
        cursor = 0
        text = str(text_node)
        for match in _REFERENCE_RE.finditer(text):
            kind, number = match.group(1), match.group(2)
            if number not in numbers[kind]:
                continue
            pieces.append(text[cursor:match.start()])
            link = soup.new_tag("a", href=f"#{prefixes[kind]}-{number}")
            add_class(link, "dm-xref")
            link.string = match.group(0)
            pieces.append(link)
            cursor = match.end()

        if not pieces:
            continue
        pieces.append(text[cursor:])
        # 空文字列を残すと NavigableString が増えるだけなので落とす。
        text_node.replace_with(*[p for p in pieces if not isinstance(p, str) or p])


def _only_child(paragraph: Any, image: Any) -> bool:
    """段落の中身が画像 1 つだけか（前後の空白は許容）。"""
    for child in paragraph.contents:
        if child is image:
            continue
        if getattr(child, "name", None) is not None:
            return False
        if str(child).strip():
            return False
    return True


def _caption_from(node: Any, pattern: re.Pattern) -> str:
    match = pattern.match(node.get_text(strip=True))
    return match.group("text").strip() if match else ""


def _previous_element(tag: Any) -> Any:
    for sibling in tag.previous_siblings:
        if getattr(sibling, "name", None) is not None:
            return sibling
        if str(sibling).strip():
            return None
    return None
