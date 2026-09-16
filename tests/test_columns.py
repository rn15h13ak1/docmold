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
    """見出し 2 の 1 つ目は 1 列、2 つ目以降は列（位置で決める）。"""

    def test_subheadings_become_groups_holding_a_column_per_section(self):
        soup = run("group_columns",
                   section("トピックス", "<p>連絡</p>")
                   + section("前週", "<h3>バグ</h3><p>A</p><h3>要望</h3><p>B</p>")
                   + section("今週", "<h3>バグ</h3><p>C</p><h3>要望</h3><p>D</p>"))
        groups = soup.select(".dm-group")
        assert [tag.get_text() for tag in soup.select(".dm-group__title")] == ["バグ", "要望"]
        titles = [tag.get_text() for tag in groups[0].select(".dm-column__title")]
        assert titles == ["前週", "今週"]
        assert [tag.get_text() for tag in groups[0].select(".dm-column p:not(.dm-column__title)")] \
            == ["A", "C"]

    def test_first_section_is_kept_as_one_column(self):
        soup = run("group_columns",
                   section("トピックス", "<ul><li>連絡</li></ul>")
                   + section("前週", "<h3>バグ</h3><p>A</p>")
                   + section("今週", "<h3>バグ</h3><p>B</p>"))
        topics = soup.select_one(".dm-section")
        assert "dm-section--full" in topics["class"]
        assert topics.find("h2").get_text() == "トピックス"
        assert topics.select_one(".dm-column") is None
        # 組み替えた列は、その節より後ろに置く（本文の順序を保つ）。
        assert list(soup.children).index(topics) < list(soup.children).index(
            soup.select_one(".dm-groups"))

    def test_first_section_is_one_column_even_with_subheadings(self):
        soup = run("group_columns",
                   section("トピックス", "<h3>連絡</h3><p>A</p>")
                   + section("前週", "<h3>バグ</h3><p>B</p>")
                   + section("今週", "<h3>バグ</h3><p>C</p>"))
        # 見出しの文字列ではなく位置で決めるため、小見出しがあっても列にしない。
        assert [tag.get_text() for tag in soup.select(".dm-group__title")] == ["バグ"]
        assert "dm-section--full" in soup.select_one(".dm-section")["class"]

    def test_missing_column_is_kept_as_an_empty_slot(self):
        soup = run("group_columns",
                   section("トピックス", "<p>連絡</p>")
                   + section("前週", "<h3>バグ</h3><p>A</p>")
                   + section("今週", "<h3>バグ</h3><p>B</p><h3>要望</h3><p>C</p>"))
        request = soup.select(".dm-group")[1]
        columns = request.select(".dm-column")
        # 列の位置がずれないよう、中身が無くても枠は残す。
        assert len(columns) == 2
        assert "dm-column--empty" in columns[0]["class"]
        assert "dm-column--empty" not in columns[1]["class"]

    def test_group_order_follows_first_appearance(self):
        soup = run("group_columns",
                   section("トピックス", "<p>連絡</p>")
                   + section("前週", "<h3>B</h3><p>x</p>")
                   + section("今週", "<h3>A</h3><p>y</p><h3>B</h3><p>z</p>"))
        assert [tag.get_text() for tag in soup.select(".dm-group__title")] == ["B", "A"]

    def test_content_before_the_first_subheading_is_kept(self):
        soup = run("group_columns",
                   section("トピックス", "<p>連絡</p>")
                   + section("前週", "<p>まえがき</p><h3>バグ</h3><p>A</p>")
                   + section("今週", "<h3>バグ</h3><p>B</p>"))
        first = soup.select_one(".dm-group")
        assert first.select_one(".dm-group__title") is None
        assert "まえがき" in first.get_text()

    def test_columns_without_subheadings_are_left_as_sections(self):
        soup = run("group_columns",
                   section("トピックス", "<p>連絡</p>")
                   + section("前週", "<p>A</p>")
                   + section("今週", "<p>B</p>"))
        # 組み替えるものが無いので、節がそのまま列になる。
        assert soup.select_one(".dm-group") is None
        assert len(soup.select(".dm-section")) == 3

    def test_topics_only_is_left_alone(self):
        soup = run("group_columns", section("トピックス", "<p>連絡</p>"))
        assert soup.select_one(".dm-groups") is None
        assert "dm-section--full" in soup.select_one(".dm-section")["class"]


class TestSectionCount:
    def warnings_of(self, html: str) -> list:
        from bs4 import BeautifulSoup

        from rules import apply_rules, take_warnings

        meta: dict = {}
        apply_rules(["group_columns"], BeautifulSoup(html, "html.parser"), meta)
        return take_warnings(meta)

    def test_four_sections_are_silent(self):
        html = section("トピックス", "<p>x</p>") + "".join(
            section(name, "<h3>バグ</h3><p>A</p>") for name in ("前週", "今週", "来週"))
        assert self.warnings_of(html) == []

    def test_other_counts_are_reported(self):
        html = section("トピックス", "<p>x</p>") + section("前週", "<h3>バグ</h3><p>A</p>")
        assert "4 個" in self.warnings_of(html)[0]

    def test_warning_reaches_the_conversion_result(self, config):
        from converter import convert_text

        result = convert_text("---\ntype: columns\n---\n\n## トピックス\n\n連絡\n", config)
        assert any("見出し 2" in warning for warning in result.warnings)


class TestTopicCards:
    def full_section(self, body: str) -> str:
        return ('<section class="dm-section dm-section--full"><h2>トピックス</h2>'
                f'{body}</section>')

    def test_each_item_becomes_a_frame(self):
        soup = run("topic_cards", self.full_section("<ul><li>A</li><li>B</li></ul>"))
        assert soup.select_one(".dm-topics") is not None
        assert [tag.get_text() for tag in soup.select(".dm-topic")] == ["A", "B"]

    def test_multiple_lines_stay_inside_one_frame(self):
        soup = run("topic_cards",
                   self.full_section("<ul><li><p>見出し</p><p>本文</p></li></ul>"))
        topics = soup.select(".dm-topic")
        assert len(topics) == 1
        assert len(topics[0].find_all("p")) == 2

    def test_numbered_list_is_left_alone(self):
        soup = run("topic_cards", self.full_section("<ol><li>A</li></ol>"))
        assert soup.select_one(".dm-topic") is None

    def test_columns_are_left_alone(self):
        soup = run("topic_cards",
                   '<section class="dm-section dm-section--h2"><h2>前週</h2>'
                   "<ul><li>A</li></ul></section>")
        assert soup.select_one(".dm-topic") is None
