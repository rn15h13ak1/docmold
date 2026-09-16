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
