"""rules: ルール層 (意味づけ) の DOM 後処理。"""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from rules import RULES, RuleError, apply_rules, derived, rule_descriptions, unknown_rules


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def run(name: str, html: str, meta: dict = None):
    """1 ルールだけを適用して (soup, meta) を返す。"""
    soup, data = soup_of(html), dict(meta or {})
    apply_rules([name], soup, data)
    return soup, data


class TestRegistry:
    def test_bundled_rules_are_registered(self):
        assert unknown_rules(["todo_checklist", "timeline_table"]) == set()

    def test_unknown_rule_is_reported(self):
        assert unknown_rules(["nope"]) == {"nope"}

    def test_apply_unknown_rule_raises(self):
        with pytest.raises(RuleError, match="未登録のルール"):
            apply_rules(["nope"], soup_of("<p>x</p>"), {})

    def test_failure_names_the_rule(self, monkeypatch):
        monkeypatch.setitem(RULES, "boom", lambda soup, meta: 1 / 0)
        with pytest.raises(RuleError, match="'boom'"):
            apply_rules(["boom"], soup_of("<p>x</p>"), {})

    def test_every_rule_has_a_description(self):
        assert all(description for _, description in rule_descriptions())


class TestMinutes:
    def test_todo_list_gets_checkboxes(self):
        soup, _ = run("todo_checklist", "<h2>ToDo</h2><ul><li>資料作成</li></ul>")
        assert soup.find("input", {"type": "checkbox"}) is not None

    def test_task_marker_sets_checked(self):
        soup, _ = run("todo_checklist", "<h2>ToDo</h2><ul><li>[x] 完了分</li></ul>")
        box = soup.find("input")
        assert box.has_attr("checked")
        assert "[x]" not in soup.get_text()

    def test_checkbox_is_disabled(self):
        """配布物の状態は Markdown 側の記述で固定する。"""
        soup, _ = run("todo_checklist", "<h2>ToDo</h2><ul><li>[ ] 未完</li></ul>")
        assert soup.find("input").has_attr("disabled")

    def test_owner_becomes_badge(self):
        soup, _ = run("todo_checklist", "<h2>ToDo</h2><ul><li>周知文面 担当: 山田</li></ul>")
        badge = soup.find("span", class_="dm-badge")
        assert badge is not None and badge.get_text() == "山田"
        assert "担当:" not in soup.get_text()

    def test_at_mention_becomes_badge(self):
        soup, _ = run("todo_checklist", "<h2>ToDo</h2><ul><li>周知文面 @山田</li></ul>")
        assert soup.find("span", class_="dm-badge").get_text() == "山田"

    def test_marker_outside_todo_section_still_works(self):
        soup, _ = run("todo_checklist", "<h2>その他</h2><ul><li>[ ] 宿題</li></ul>")
        assert soup.find("input", {"type": "checkbox"}) is not None

    def test_plain_list_outside_todo_is_untouched(self):
        soup, _ = run("todo_checklist", "<h2>議論</h2><ul><li>ただの箇条書き</li></ul>")
        assert soup.find("input") is None

    def test_attendee_list_is_badged(self):
        soup, _ = run("attendee_table", "<h2>出席者</h2><ul><li>山田</li><li>佐藤</li></ul>")
        assert soup.find("ul", class_="dm-attendees") is not None

    def test_decision_section_is_wrapped(self):
        soup, _ = run("decision_highlight", "<h2>決定事項</h2><ul><li>10/18 に実施</li></ul>")
        box = soup.find("div", class_="dm-callout--decision")
        assert box is not None and "10/18" in box.get_text()


class TestProcedure:
    def test_steps_are_numbered(self):
        html = "<h2>手順 1: 停止</h2><p>a</p><h2>手順 2: 切替</h2><p>b</p>"
        soup, _ = run("step_numbering", html)
        numbers = [tag.get_text() for tag in soup.find_all("span", class_="dm-step__number")]
        assert numbers == ["1", "2"]

    def test_step_content_stays_inside_card(self):
        soup, _ = run("step_numbering", "<h2>手順 1</h2><p>実施内容</p><h2>手順 2</h2>")
        first = soup.find("section", class_="dm-step")
        assert "実施内容" in first.get_text()

    def test_step_has_check_control(self):
        soup, _ = run("step_numbering", "<h2>手順 1</h2><p>a</p>")
        assert soup.find("label", class_="dm-step__check") is not None

    def test_falls_back_to_second_level_headings(self):
        """「手順」と書かれていなくても、本文の見出し単位でカードにする。"""
        soup, _ = run("step_numbering", "<h1>表題</h1><h2>停止</h2><p>a</p><h2>切替</h2><p>b</p>")
        assert len(soup.find_all("section", class_="dm-step")) == 2

    def test_copy_button_targets_the_block(self):
        soup, _ = run("command_block_copy", "<pre><code>ls -l</code></pre>")
        button = soup.find("button", class_="dm-code__copy")
        assert button["data-dm-copy"] == soup.find("pre")["id"]

    def test_copy_button_is_not_added_twice(self):
        soup, meta = run("command_block_copy", "<pre><code>ls</code></pre>")
        apply_rules(["command_block_copy"], soup, meta)
        assert len(soup.find_all("button", class_="dm-code__copy")) == 1

    def test_rollback_is_not_numbered_as_a_step(self):
        """切戻しは異常時だけの復旧手順なので、通し番号に含めない。"""
        html = "<h2>手順 1: 停止</h2><p>a</p><h2>手順 2: 切替</h2><p>b</p><h2>切戻し手順</h2><p>c</p>"
        soup, _ = run("step_numbering", html)
        numbers = [tag.get_text() for tag in soup.find_all("span", class_="dm-step__number")]
        assert numbers == ["1", "2"]
        assert "切戻し手順" not in soup.find_all("section", class_="dm-step")[-1].get_text()

    def test_rollback_is_excluded_from_fallback_headings(self):
        html = "<h1>表題</h1><h2>停止</h2><p>a</p><h2>ロールバック</h2><p>b</p>"
        soup, _ = run("step_numbering", html)
        assert len(soup.find_all("section", class_="dm-step")) == 1

    def test_rollback_section_is_called_out(self):
        soup, _ = run("rollback_callout", "<h2>切戻し手順</h2><p>元に戻す</p>")
        box = soup.find("div", class_="dm-callout--rollback")
        assert box is not None and "元に戻す" in box.get_text()


class TestIncident:
    def test_severity_from_front_matter(self):
        _, meta = run("severity_badge", "<p>本文</p>", {"重要度": "高"})
        assert derived(meta)["severity"] == {"text": "高", "kind": "danger"}

    def test_severity_column_is_badged(self):
        html = ("<table><tr><th>業務</th><th>重要度</th></tr>"
                "<tr><td>受注</td><td>高</td></tr></table>")
        soup, _ = run("severity_badge", html)
        assert soup.find("span", class_="dm-badge--danger").get_text() == "高"

    def test_summary_cards_from_front_matter(self):
        meta = {"発生日時": "2026-09-10 14:22", "復旧日時": "2026-09-10 16:05",
                "影響範囲": "受注登録画面", "重要度": "高"}
        _, data = run("impact_summary", "<p>本文</p>", meta)
        labels = [card["label"] for card in derived(data)["summary"]]
        assert labels == ["発生", "復旧", "影響範囲", "重要度"]

    def test_summary_skips_missing_fields(self):
        _, data = run("impact_summary", "<p>本文</p>", {"発生日時": "14:22"})
        assert [card["label"] for card in derived(data)["summary"]] == ["発生"]

    def test_timeline_replaces_table(self):
        html = ("<table><tr><th>時刻</th><th>対応</th></tr>"
                "<tr><td>14:22</td><td>検知</td></tr>"
                "<tr><td>16:05</td><td>復旧</td></tr></table>")
        soup, _ = run("timeline_table", html)
        assert soup.find("table") is None
        items = soup.find_all("li", class_="dm-timeline__item")
        assert len(items) == 2
        assert items[0].find("span", class_="dm-timeline__time").get_text() == "14:22"

    def test_table_without_time_column_is_kept(self):
        soup, _ = run("timeline_table", "<table><tr><th>業務</th></tr><tr><td>受注</td></tr></table>")
        assert soup.find("table") is not None


class TestSpec:
    def test_figure_is_numbered(self):
        soup, meta = run("figure_caption", '<p><img src="a.png" alt="全体構成"></p>')
        caption = soup.find("figcaption")
        assert caption.get_text() == "図 1: 全体構成"
        assert soup.find("figure")["id"] == "fig-1"
        assert derived(meta)["figures"][0]["number"] == "1"

    def test_table_caption_from_preceding_paragraph(self):
        html = "<p>表: 機器一覧</p><table><tr><th>機器</th></tr></table>"
        soup, _ = run("table_caption", html)
        assert soup.find("caption").get_text() == "表 1: 機器一覧"
        assert soup.find("p") is None  # キャプション元の段落は残さない

    def test_tables_are_numbered_in_order(self):
        html = "<table><tr><th>A</th></tr></table><table><tr><th>B</th></tr></table>"
        soup, _ = run("table_caption", html)
        assert [t["id"] for t in soup.find_all("table")] == ["tbl-1", "tbl-2"]

    def test_cross_reference_links_to_numbered_table(self):
        soup = soup_of("<p>詳細は表 1 を参照。</p><table><tr><th>A</th></tr></table>")
        meta = {}
        apply_rules(["table_caption", "cross_reference"], soup, meta)
        link = soup.find("a", class_="dm-xref")
        assert link is not None and link["href"] == "#tbl-1"

    def test_unnumbered_reference_is_left_as_text(self):
        soup = soup_of("<p>詳細は表 9 を参照。</p><table><tr><th>A</th></tr></table>")
        apply_rules(["table_caption", "cross_reference"], soup, {})
        assert soup.find("a", class_="dm-xref") is None

    def test_caption_text_is_not_linked(self):
        soup = soup_of("<p>表: 一覧</p><table><tr><th>A</th></tr></table>")
        apply_rules(["table_caption", "cross_reference"], soup, {})
        assert soup.find("a", class_="dm-xref") is None


class TestWeekly:
    def test_status_column_is_badged(self):
        html = ("<table><tr><th>タスク</th><th>状態</th></tr>"
                "<tr><td>設計</td><td>完了</td></tr>"
                "<tr><td>試験</td><td>未着手</td></tr></table>")
        soup, _ = run("status_badge", html)
        kinds = [b["class"][1] for b in soup.find_all("span", class_="dm-badge")]
        assert kinds == ["dm-badge--ok", "dm-badge--danger"]

    def test_progress_becomes_bar(self):
        html = ("<table><tr><th>タスク</th><th>進捗</th></tr>"
                "<tr><td>設計</td><td>60%</td></tr></table>")
        soup, _ = run("progress_bar", html)
        fill = soup.find("span", class_="dm-progress__fill")
        assert fill["style"] == "width: 60%;"
        assert "60%" in soup.get_text()

    def test_full_width_percent(self):
        html = "<table><tr><th>進捗</th></tr><tr><td>１００％</td></tr></table>"
        soup, _ = run("progress_bar", html)
        assert soup.find("span", class_="dm-progress__fill")["style"] == "width: 100%;"

    def test_non_numeric_cell_is_left_alone(self):
        html = "<table><tr><th>進捗</th></tr><tr><td>未定</td></tr></table>"
        soup, _ = run("progress_bar", html)
        assert soup.find("span", class_="dm-progress") is None


class TestDiagramNumbering:
    """Mermaid の図も表と同じように採番する（設計書で図表番号を使うため）。"""

    def _diagram(self, caption: str = "") -> str:
        head = f"<p>{caption}</p>" if caption else ""
        return f'{head}<pre class="mermaid">graph TD\n  A --&gt; B</pre>'

    def test_diagram_is_numbered(self):
        soup, meta = run("figure_caption", self._diagram("図: 全体構成"))
        assert soup.find("figcaption").get_text() == "図 1: 全体構成"
        assert soup.find("figure")["id"] == "fig-1"

    def test_definition_is_kept(self):
        soup, _ = run("figure_caption", self._diagram("図: 全体構成"))
        assert soup.find("pre", class_="mermaid") is not None
        assert "graph TD" in soup.get_text()

    def test_caption_paragraph_is_consumed(self):
        soup, _ = run("figure_caption", self._diagram("図: 全体構成"))
        assert soup.find("p") is None

    def test_diagram_without_caption(self):
        soup, _ = run("figure_caption", self._diagram())
        assert soup.find("figcaption").get_text() == "図 1"

    def test_unrelated_paragraph_is_kept(self):
        soup, _ = run("figure_caption", "<p>本文</p>" + self._diagram())
        assert soup.find("p").get_text() == "本文"

    def test_images_and_diagrams_share_the_numbering(self):
        html = '<p><img src="a.png" alt="配置図"></p>' + self._diagram("図: 流れ")
        soup, meta = run("figure_caption", html)
        captions = [tag.get_text() for tag in soup.find_all("figcaption")]
        assert captions == ["図 1: 配置図", "図 2: 流れ"]

    def test_plain_code_block_is_not_numbered(self):
        soup, _ = run("figure_caption", "<pre><code>ls -l</code></pre>")
        assert soup.find("figure") is None

    def test_cross_reference_links_to_the_diagram(self):
        soup = soup_of("<p>構成を図 1 に示す。</p>" + self._diagram("図: 全体構成"))
        apply_rules(["figure_caption", "cross_reference"], soup, {})
        assert soup.find("a", class_="dm-xref")["href"] == "#fig-1"
