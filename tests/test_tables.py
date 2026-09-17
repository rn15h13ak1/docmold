"""rules/tables.py: 箇条書きを表にする。"""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from converter import convert_text
from rules import apply_rules, take_warnings


def build(body: str) -> tuple:
    """Markdown 相当の HTML にルールを当て、(表, 警告) を返す。"""
    soup, meta = BeautifulSoup(body, "html.parser"), {}
    apply_rules(["list_table"], soup, meta)
    return soup.find("table"), take_warnings(meta)


def rows_of(table) -> list:
    return [[cell.get_text(strip=True) for cell in row.find_all("td")]
            for row in table.select("tbody tr")]


MARKER = "<p>表: 作業｜担当｜状態</p>"


class TestColumns:
    def test_children_fill_columns_in_order(self):
        table, warnings = build(MARKER + "<ul><li>確認<ul><li>鈴木</li><li>完了</li></ul></li></ul>")
        assert [th.get_text() for th in table.select("th")] == ["作業", "担当", "状態"]
        assert rows_of(table) == [["確認", "鈴木", "完了"]]
        assert warnings == []

    def test_dash_leaves_the_column_empty(self):
        table, warnings = build(MARKER + "<ul><li>確認<ul><li>-</li><li>完了</li></ul></li></ul>")
        assert rows_of(table) == [["確認", "", "完了"]]
        assert warnings == []

    def test_named_child_goes_to_that_column(self):
        table, warnings = build(MARKER + "<ul><li>確認<ul><li>状態: 完了</li></ul></li></ul>")
        assert rows_of(table) == [["確認", "", "完了"]]
        # 名前で飛ばしたときは数え間違いではないので警告しない。
        assert warnings == []

    def test_named_and_positional_mix(self):
        table, _ = build(MARKER + "<ul><li>確認<ul><li>状態: 完了</li><li>鈴木</li></ul></li></ul>")
        # 名前を書いた行が先でも、残りは空いている列に入る。
        assert rows_of(table) == [["確認", "鈴木", "完了"]]

    def test_unknown_label_is_treated_as_a_value(self):
        table, _ = build(MARKER + "<ul><li>確認<ul><li>期限: 3/20</li><li>完了</li></ul></li></ul>")
        assert rows_of(table) == [["確認", "期限: 3/20", "完了"]]

    def test_item_without_children_is_one_column(self):
        table, warnings = build(MARKER + "<ul><li>確認</li></ul>")
        assert rows_of(table) == [["確認", "", ""]]
        assert "3 列のところ 1 個" in warnings[0]

    def test_too_many_children_are_reported(self):
        table, warnings = build(
            MARKER + "<ul><li>確認<ul><li>鈴木</li><li>完了</li><li>余り</li></ul></li></ul>")
        assert rows_of(table) == [["確認", "鈴木", "完了"]]
        assert "3 列のところ 4 個" in warnings[0]

    def test_warning_names_the_row(self):
        _, warnings = build(MARKER + "<ul><li>A</li><li>B<ul><li>鈴木</li></ul></li></ul>")
        assert "表「作業」の 1 行目" in warnings[0]
        assert "2 行目" in warnings[1]


class TestMarker:
    def test_list_without_a_marker_is_left_alone(self):
        table, _ = build("<ul><li>確認<ul><li>鈴木</li></ul></li></ul>")
        assert table is None

    def test_marker_not_followed_by_a_list_is_left_alone(self):
        """``表: 説明`` を表のキャプションとして書く使い方を壊さないこと。"""
        soup = BeautifulSoup("<p>表: 準備の一覧</p><table><tr><td>x</td></tr></table>",
                             "html.parser")
        apply_rules(["list_table"], soup, {})
        assert soup.find("p") is not None

    def test_single_column_is_not_a_marker(self):
        table, _ = build("<p>表: 作業</p><ul><li>確認</li></ul>")
        assert table is None

    def test_other_words_are_not_markers(self):
        table, _ = build("<p>参考: 作業｜担当</p><ul><li>確認</li></ul>")
        assert table is None

    def test_half_width_pipe_works(self):
        table, _ = build("<p>表: 作業|担当</p><ul><li>確認<ul><li>鈴木</li></ul></li></ul>")
        assert rows_of(table) == [["確認", "鈴木"]]

    def test_decorated_marker_is_left_alone(self):
        table, _ = build("<p><strong>表: 作業｜担当</strong></p><ul><li>確認</li></ul>")
        assert table is None


class TestContent:
    def test_links_inside_cells_are_kept(self):
        table, _ = build(
            MARKER + '<ul><li><a href="x.html">確認</a><ul><li>鈴木</li></ul></li></ul>')
        assert table.select_one("td a")["href"] == "x.html"

    def test_badge_written_in_the_cell_is_kept(self):
        table, _ = build(
            MARKER + '<ul><li>確認<ul><li><span class="dm-badge">任意</span></li></ul></li></ul>')
        assert table.select_one("td .dm-badge") is not None


class TestInDocument:
    @pytest.fixture
    def document(self, config):
        text = ("---\ntype: weekly3\ntitle: t\n開始日: 2026-03-09\n---\n\n"
                "## トピックス\n\n### 準備\n\n"
                "表: 準備作業｜担当｜進捗｜状態\n\n"
                "- 手順の最終確認\n    - 鈴木\n    - 80%\n    - 進行中\n\n"
                "## 前週\n\n### バグ\n\n本文\n\n## 今週\n\n### バグ\n\n本文\n"
                "\n## 来週\n\n### バグ\n\n本文\n")
        return convert_text(text, config)

    def test_marker_line_is_consumed(self, document):
        assert "表: 準備作業" not in document.html
        assert document.warnings == []

    def test_existing_rules_apply_to_the_built_table(self, document):
        # 変換後は普通の表なので、状態はバッジ、進捗はバーになる。
        assert 'class="dm-badge dm-badge--warn"' in document.html
        assert 'class="dm-progress__fill"' in document.html


class TestListsInCells:
    def test_nested_list_stays_in_the_cell(self):
        table, warnings = build(
            MARKER + "<ul><li>確認<ul><li>鈴木</li>"
            "<li>次の 2 点<ul><li>A</li><li>B</li></ul></li></ul></li></ul>")
        cell = table.select("tbody td")[2]
        assert cell.get_text(strip=True).startswith("次の 2 点")
        assert [li.get_text() for li in cell.select("ul li")] == ["A", "B"]
        assert warnings == []

    def test_dash_makes_the_cell_a_list_only(self):
        table, warnings = build(
            MARKER + "<ul><li>確認<ul><li>鈴木</li>"
            "<li>-<ul><li>A</li><li>B</li></ul></li></ul></li></ul>")
        cell = table.select("tbody td")[2]
        # 「-」の文字は残さず、箇条書きだけを入れる。
        assert cell.find("ul") is not None
        assert "-" not in cell.get_text()
        assert warnings == []

    def test_dash_without_a_list_is_still_empty(self):
        table, _ = build(MARKER + "<ul><li>確認<ul><li>-</li><li>完了</li></ul></li></ul>")
        assert rows_of(table) == [["確認", "", "完了"]]

    def test_cell_list_counts_as_one_column(self):
        _, warnings = build(
            MARKER + "<ul><li>確認<ul><li>鈴木</li>"
            "<li>-<ul><li>A</li></ul></li></ul></li></ul>")
        assert warnings == []

    def test_from_markdown(self, config):
        text = ("---\ntype: weekly3\ntitle: t\n開始日: 2026-03-09\n---\n\n"
                "## トピックス\n\n### x\n\n"
                "表: 作業｜担当｜補足\n\n"
                "- 手順の最終確認\n    - 鈴木\n    - 次の 2 点\n"
                "        - 3/19 に共有済み\n        - 再現条件を確認中\n"
                "- 連絡体制の確認\n    - 田中\n    - -\n        - 窓口を 1 名増やす\n\n"
                "## 前週\n\n### バグ\n\n本文\n\n## 今週\n\n### バグ\n\n本文\n"
                "\n## 来週\n\n### バグ\n\n本文\n")
        result = convert_text(text, config)
        assert result.warnings == []
        table = BeautifulSoup(result.html, "html.parser").select_one("table.dm-table")
        cells = [cell for cell in table.select("tbody td")]
        assert cells[2].select("ul li")[0].get_text() == "3/19 に共有済み"
        assert cells[5].select("ul li")[0].get_text() == "窓口を 1 名増やす"
