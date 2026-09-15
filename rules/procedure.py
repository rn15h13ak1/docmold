"""作業手順書 (procedure) のルール。"""
from __future__ import annotations

from typing import Any, Dict

from rules import keywords, rule
from rules.common import (
    add_class, find_headings, heading_level, make_callout, normalize, section_nodes,
    wrap_section,
)


@rule("step_numbering")
def step_numbering(soup: Any, meta: Dict[str, Any]) -> None:
    """手順の見出しを ``<section>`` カードにまとめ、自動採番とチェック欄を付ける。"""
    headings = _step_headings(soup)
    for number, heading in enumerate(headings, start=1):
        card = wrap_section(soup, heading, "dm-step")
        card["id"] = card.get("id") or f"step-{number}"

        label = soup.new_tag("span")
        add_class(label, "dm-step__number")
        label.string = str(number)
        heading.insert(0, label)
        add_class(heading, "dm-step__title")

        check = soup.new_tag("label")
        add_class(check, "dm-step__check")
        box = soup.new_tag("input", attrs={"type": "checkbox"})
        add_class(box, "dm-check")
        check.append(box)
        done = soup.new_tag("span")
        done.string = "完了"
        check.append(done)
        heading.append(check)


@rule("command_block_copy")
def command_block_copy(soup: Any, meta: Dict[str, Any]) -> None:
    """コードブロックにコピーボタンを付ける（JS はテンプレートに埋め込み済み）。"""
    for index, pre in enumerate(soup.find_all("pre"), start=1):
        if pre.find_parent("div", class_="dm-code") is not None:
            continue
        wrapper = soup.new_tag("div")
        add_class(wrapper, "dm-code")
        button = soup.new_tag("button", attrs={"type": "button"})
        add_class(button, "dm-code__copy")
        button["data-dm-copy"] = f"code-{index}"
        button.string = "コピー"

        pre["id"] = pre.get("id") or f"code-{index}"
        pre.insert_before(wrapper)
        wrapper.append(button)
        wrapper.append(pre.extract())


@rule("rollback_callout")
def rollback_callout(soup: Any, meta: Dict[str, Any]) -> None:
    """「切戻し手順」節を警告コールアウトにして目立たせる。"""
    for heading in find_headings(soup, keywords.get("rollback")):
        nodes = section_nodes(heading)
        box = make_callout(soup, "rollback", "切戻し手順")
        heading.insert_after(box)
        for node in nodes:
            box.append(node.extract())


def _step_headings(soup: Any) -> list:
    """手順の単位となる見出しを選ぶ。

    「手順」「Step」を含む見出しがあればそれを使う。無ければ本文の最上位より
    1 段下の見出し（多くは ``h2``）を手順とみなす。
    """
    explicit = _without_rollback(find_headings(soup, keywords.get("step")))
    if explicit:
        return explicit

    levels = sorted({heading_level(h) for h in soup.find_all(["h1", "h2", "h3"])} - {0})
    if not levels:
        return []
    target = levels[1] if len(levels) > 1 and levels[0] == 1 else levels[0]
    return _without_rollback(soup.find_all(f"h{target}"))


def _without_rollback(headings: list) -> list:
    """切戻し手順を通し番号から外す。

    「切戻し手順」は 手順 1 → 2 → 3 と続く作業の一部ではなく、異常時にだけ実施する
    復旧手順。番号を振ると「最後に必ず実施する手順」に見えてしまう。
    """
    rollback = [normalize(word) for word in keywords.get("rollback")]
    return [
        heading for heading in headings
        if not any(word in normalize(heading.get_text()) for word in rollback)
    ]
