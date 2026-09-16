"""rules/columns.py: 列並べで使うルール。"""
from __future__ import annotations

from bs4 import BeautifulSoup

from rules import apply_rules


def run(name: str, html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    apply_rules([name], soup, {})
    return soup


class TestEntryCard:
    def test_fields_become_key_meta_and_body(self):
        soup = run("entry_card", "<ul><li>AB-1｜期限：3/20｜処理中｜一覧表示が遅い</li></ul>")
        assert soup.select_one(".dm-entry__key").get_text() == "AB-1"
        assert soup.select_one(".dm-entry__meta").get_text() == "期限：3/20"
        assert soup.select_one(".dm-entry__body").get_text() == "一覧表示が遅い"

    def test_status_field_becomes_a_badge(self):
        soup = run("entry_card", "<ul><li>AB-1｜完了｜対応した</li></ul>")
        badge = soup.select_one(".dm-badge")
        assert badge.get_text() == "完了"
        assert "dm-badge--ok" in badge["class"]

    def test_half_width_separator_works_too(self):
        soup = run("entry_card", "<ul><li>AB-1|未対応|見出し</li></ul>")
        assert soup.select_one(".dm-entry__key").get_text() == "AB-1"
        assert soup.select_one(".dm-badge").get_text() == "未対応"

    def test_two_fields_are_key_and_body(self):
        soup = run("entry_card", "<ul><li>AB-1｜一覧表示が遅い</li></ul>")
        assert soup.select_one(".dm-entry__key").get_text() == "AB-1"
        assert soup.select_one(".dm-entry__body").get_text() == "一覧表示が遅い"
        assert soup.select_one(".dm-entry__meta") is None

    def test_empty_last_field_leaves_no_body(self):
        soup = run("entry_card", "<ul><li>AB-1｜処理中｜</li></ul>")
        assert soup.select_one(".dm-entry__body") is None
        assert soup.select_one(".dm-badge").get_text() == "処理中"

    def test_links_inside_a_field_are_kept(self):
        soup = run("entry_card", '<ul><li><a href="x.html">AB-1</a>｜一覧表示が遅い</li></ul>')
        link = soup.select_one(".dm-entry__key a")
        assert link is not None and link["href"] == "x.html"

    def test_items_without_a_separator_are_left_alone(self):
        soup = run("entry_card", "<ul><li>ただの箇条書き</li></ul>")
        assert soup.select_one(".dm-entry") is None
        assert soup.select_one(".dm-entries") is None

    def test_nested_list_is_left_alone(self):
        soup = run("entry_card", "<ul><li>親｜子<ul><li>孫</li></ul></li></ul>")
        assert soup.select_one(".dm-entry") is None


class TestCountSummary:
    def test_pairs_become_counts(self):
        soup = run("count_summary", "<p>残:3 / 新規:1 / 完了:2</p>")
        labels = [tag.get_text() for tag in soup.select(".dm-count__label")]
        values = [tag.get_text() for tag in soup.select(".dm-count__value")]
        assert labels == ["残", "新規", "完了"]
        assert values == ["3", "1", "2"]

    def test_full_width_punctuation_works_too(self):
        soup = run("count_summary", "<p>残：3／新規：1</p>")
        assert [tag.get_text() for tag in soup.select(".dm-count__value")] == ["3", "1"]

    def test_a_single_pair_is_left_alone(self):
        soup = run("count_summary", "<p>所要時間: 30</p>")
        assert soup.select_one(".dm-counts") is None

    def test_a_sentence_is_left_alone(self):
        soup = run("count_summary", "<p>残:3 件あります / 新規:1</p>")
        assert soup.select_one(".dm-counts") is None

    def test_decorated_paragraph_is_left_alone(self):
        soup = run("count_summary", "<p><strong>残:3</strong> / 新規:1</p>")
        assert soup.select_one(".dm-counts") is None


def section(title: str, body: str) -> str:
    """_wrap_sections が作るのと同じ節を組み立てる。"""
    return f'<section class="dm-section dm-section--h2"><h2>{title}</h2>{body}</section>'


class TestGroupColumns:
    def test_subheadings_become_groups_holding_a_column_per_section(self):
        soup = run("group_columns",
                   section("前週", "<h3>バグ</h3><p>A</p><h3>要望</h3><p>B</p>")
                   + section("今週", "<h3>バグ</h3><p>C</p><h3>要望</h3><p>D</p>"))
        groups = soup.select(".dm-group")
        assert [tag.get_text() for tag in soup.select(".dm-group__title")] == ["バグ", "要望"]
        titles = [tag.get_text() for tag in groups[0].select(".dm-column__title")]
        assert titles == ["前週", "今週"]
        assert [tag.get_text() for tag in groups[0].select(".dm-column p:not(.dm-column__title)")] \
            == ["A", "C"]

    def test_missing_column_is_kept_as_an_empty_slot(self):
        soup = run("group_columns",
                   section("前週", "<h3>バグ</h3><p>A</p>")
                   + section("今週", "<h3>バグ</h3><p>B</p><h3>連絡</h3><p>C</p>"))
        notice = soup.select(".dm-group")[1]
        columns = notice.select(".dm-column")
        # 列の位置がずれないよう、中身が無くても枠は残す。
        assert len(columns) == 2
        assert "dm-column--empty" in columns[0]["class"]
        assert "dm-column--empty" not in columns[1]["class"]

    def test_group_order_follows_first_appearance(self):
        soup = run("group_columns",
                   section("前週", "<h3>B</h3><p>x</p>")
                   + section("今週", "<h3>A</h3><p>y</p><h3>B</h3><p>z</p>"))
        assert [tag.get_text() for tag in soup.select(".dm-group__title")] == ["B", "A"]

    def test_content_before_the_first_subheading_is_kept(self):
        soup = run("group_columns",
                   section("前週", "<p>まえがき</p><h3>バグ</h3><p>A</p>")
                   + section("今週", "<h3>バグ</h3><p>B</p>"))
        first = soup.select_one(".dm-group")
        assert first.select_one(".dm-group__title") is None
        assert "まえがき" in first.get_text()

    def test_document_without_subheadings_is_left_alone(self):
        html = section("前週", "<p>A</p>") + section("今週", "<p>B</p>")
        soup = run("group_columns", html)
        assert soup.select_one(".dm-group") is None
        assert len(soup.select(".dm-section")) == 2

    def test_single_section_is_left_alone(self):
        soup = run("group_columns", section("前週", "<h3>バグ</h3><p>A</p>"))
        assert soup.select_one(".dm-group") is None

    def test_section_without_subheadings_stays_as_one_column(self):
        soup = run("group_columns",
                   section("トピックス", "<ul><li>連絡</li></ul>")
                   + section("前週", "<h3>バグ</h3><p>A</p>")
                   + section("今週", "<h3>バグ</h3><p>B</p>"))
        topics = soup.select_one(".dm-section")
        # 列にはせず、横幅いっぱいに置くための印を付ける。
        assert "dm-section--full" in topics["class"]
        assert topics.find("h2").get_text() == "トピックス"
        assert topics.select_one(".dm-column") is None
        # 組み替えた列は、その節より後ろに置く（本文の順序を保つ）。
        assert soup.select_one(".dm-groups") is not None
        assert list(soup.children).index(topics) < list(soup.children).index(
            soup.select_one(".dm-groups"))

    def test_one_column_section_leaves_everything_alone(self):
        soup = run("group_columns",
                   section("トピックス", "<p>連絡</p>")
                   + section("前週", "<h3>バグ</h3><p>A</p>"))
        assert soup.select_one(".dm-groups") is None
        assert soup.select_one(".dm-section--full") is None


class TestColumnsProfile:
    def test_sample_is_grouped_by_subheading(self, config):
        from converter import convert_text

        result = convert_text(
            "---\ntype: columns\ntitle: 課題\n---\n\n"
            "## 前週\n\n### バグ対応\n\n残:1 / 完了:0\n\n- AB-1｜処理中｜遅い\n\n"
            "## 今週\n\n### バグ対応\n\n残:1 / 完了:1\n\n- AB-1｜完了｜遅い\n",
            config,
        )
        assert result.profile_name == "columns"
        assert result.html.count('class="dm-group__title"') == 1
        assert result.html.count('class="dm-column__title"') == 2
