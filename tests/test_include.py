"""include: front matter に並べた .md を本文に差し込む。"""
from __future__ import annotations

from pathlib import Path

import pytest

from converter import convert_file, convert_text
from include import expand


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """親 1 つと、サブディレクトリに置いた子 3 つ。"""
    for name in ("2026-03-09", "2026-03-16", "2026-03-23"):
        write(tmp_path / "parts" / f"{name}.md",
              f"---\ntype: fragment\n---\n\n### バグ対応\n\n- AB-1｜処理中｜{name}\n")
    return write(tmp_path / "週報.md",
                 "---\ntype: weekly3\ntitle: t\n開始日: 2026-03-16\n"
                 "取り込み:\n"
                 "  前週: parts/2026-03-09.md\n"
                 "  今週: parts/2026-03-16.md\n"
                 "  来週の予定: parts/2026-03-23.md\n---\n\n"
                 "## トピックス\n\n### 連絡\n\n本文\n")


class TestExpand:
    def test_each_entry_becomes_a_section(self, tmp_path):
        write(tmp_path / "parts" / "子.md", "### 中身\n")
        parent = write(tmp_path / "親.md", "本文\n")
        body, warnings = expand({"取り込み": {"前週": "parts/子.md"}},
                                "本文", parent)
        assert "## 前週" in body
        assert "### 中身" in body
        assert warnings == []

    def test_order_follows_the_front_matter(self, tmp_path):
        for name in ("a", "b"):
            write(tmp_path / f"{name}.md", f"### {name}\n")
        parent = write(tmp_path / "親.md", "本文\n")
        body, _ = expand({"取り込み": {"1 つ目": "a.md", "2 つ目": "b.md"}}, "本文", parent)
        assert body.index("## 1 つ目") < body.index("## 2 つ目")

    def test_body_comes_first(self, tmp_path):
        write(tmp_path / "子.md", "### 中身\n")
        parent = write(tmp_path / "親.md", "本文\n")
        body, _ = expand({"取り込み": {"前週": "子.md"}}, "## トピックス\n", parent)
        assert body.startswith("## トピックス")

    def test_child_front_matter_is_dropped(self, tmp_path):
        write(tmp_path / "子.md", "---\ntype: fragment\n---\n\n### 中身\n")
        parent = write(tmp_path / "親.md", "本文\n")
        body, _ = expand({"取り込み": {"前週": "子.md"}}, "本文", parent)
        assert "type: fragment" not in body

    def test_english_key_works(self, tmp_path):
        write(tmp_path / "子.md", "### 中身\n")
        parent = write(tmp_path / "親.md", "本文\n")
        body, _ = expand({"include": {"前週": "子.md"}}, "本文", parent)
        assert "### 中身" in body

    def test_document_without_the_key_is_untouched(self, tmp_path):
        parent = write(tmp_path / "親.md", "本文\n")
        body, warnings = expand({"title": "t"}, "本文", parent)
        assert (body, warnings) == ("本文", [])


class TestRelativePaths:
    def test_child_relative_links_are_moved(self, tmp_path):
        write(tmp_path / "parts" / "子.md", "![図](図/構成.png) と [設計書](設計.md)\n")
        parent = write(tmp_path / "親.md", "本文\n")
        body, _ = expand({"取り込み": {"前週": "parts/子.md"}}, "本文", parent)
        # 親から見た位置に直す（子を別のディレクトリに置けるようにするため）。
        assert "parts/図/構成.png" in body
        assert "parts/設計.md" in body

    def test_external_links_are_kept(self, tmp_path):
        write(tmp_path / "parts" / "子.md", "[外](https://example.com/a) [中](#節)\n")
        parent = write(tmp_path / "親.md", "本文\n")
        body, _ = expand({"取り込み": {"前週": "parts/子.md"}}, "本文", parent)
        assert "https://example.com/a" in body
        assert "(#節)" in body

    def test_same_directory_needs_no_change(self, tmp_path):
        write(tmp_path / "子.md", "![図](図/構成.png)\n")
        parent = write(tmp_path / "親.md", "本文\n")
        body, _ = expand({"取り込み": {"前週": "子.md"}}, "本文", parent)
        assert "![図](図/構成.png)" in body


class TestProblems:
    def expand_one(self, tmp_path, target: str):
        parent = write(tmp_path / "親.md", "本文\n")
        return expand({"取り込み": {"前週": target}}, "本文", parent)

    def test_missing_file_keeps_the_heading(self, tmp_path):
        body, warnings = self.expand_one(tmp_path, "無い.md")
        # 節が消えると列の数が変わるため、見出しは残す。
        assert "## 前週" in body
        assert "見つかりません" in warnings[0]

    def test_non_markdown_is_reported(self, tmp_path):
        _, warnings = self.expand_one(tmp_path, "表.xlsx")
        assert ".md だけ" in warnings[0]

    def test_url_is_reported(self, tmp_path):
        _, warnings = self.expand_one(tmp_path, "https://example.com/a.md")
        assert "相対パス" in warnings[0]

    def test_absolute_path_is_reported(self, tmp_path):
        _, warnings = self.expand_one(tmp_path, "/etc/passwd.md")
        assert "相対パス" in warnings[0]

    def test_self_reference_is_reported(self, tmp_path):
        parent = write(tmp_path / "親.md", "本文\n")
        _, warnings = expand({"取り込み": {"前週": "親.md"}}, "本文", parent)
        assert "自分自身" in warnings[0]

    def test_list_form_is_reported(self, tmp_path):
        parent = write(tmp_path / "親.md", "本文\n")
        _, warnings = expand({"取り込み": ["a.md"]}, "本文", parent)
        assert "見出し: パス" in warnings[0]

    def test_without_a_path_it_is_reported(self, config):
        result = convert_text(
            "---\ntype: minutes\n取り込み:\n  前週: a.md\n---\n\n本文\n", config)
        assert any("ファイルから変換" in w for w in result.warnings)


class TestInDocument:
    def test_columns_are_built_from_the_children(self, tree, config):
        result = convert_file(tree, config)
        assert result.warnings == []
        assert result.html.count('class="dm-column__title"') == 3
        assert result.html.count('class="dm-entry__key"') == 3

    def test_column_names_come_from_the_parent(self, tree, config):
        result = convert_file(tree, config)
        assert "前週（3/9(月)〜3/15(日)）" in result.html
        # 子には位置を示す語が無い（翌週の前週として使い回せる）。
        child = (tree.parent / "parts" / "2026-03-16.md").read_text(encoding="utf-8")
        assert "前週" not in child and "今週" not in child

    def test_child_can_be_converted_on_its_own(self, tree, config):
        result = convert_file(tree.parent / "parts" / "2026-03-16.md", config)
        assert result.profile_name == "fragment"
        assert result.warnings == []
