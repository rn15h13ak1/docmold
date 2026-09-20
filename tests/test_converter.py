"""converter: 種類の判定と変換パイプライン。"""
from __future__ import annotations

from pathlib import Path

import pytest

from converter import (ConversionError, convert_file, convert_text, github_slug,
                       resolve_profile)


class TestProfileResolution:
    def test_front_matter_type(self, config):
        profile, warnings = resolve_profile(config, {"type": "minutes"})
        assert profile.name == "minutes"
        assert warnings == []

    def test_missing_type_falls_back_to_default(self, config):
        profile, warnings = resolve_profile(config, {})
        assert profile.name == "default"
        assert warnings == []

    def test_unknown_type_warns_and_uses_default(self, config):
        """タイプミスに気づけるよう、黙って default に落とさない。"""
        profile, warnings = resolve_profile(config, {"type": "minuets"})
        assert profile.name == "default"
        assert len(warnings) == 1
        assert "minuets" in warnings[0]

    def test_cli_override_wins(self, config):
        profile, warnings = resolve_profile(config, {"type": "minutes"}, type_override="spec")
        assert profile.name == "spec"
        assert warnings == []

    def test_blank_type_is_default(self, config):
        profile, _ = resolve_profile(config, {"type": "   "})
        assert profile.name == "default"


class TestConvertText:
    def test_self_contained_output(self, config):
        result = convert_text("# 見出し\n\n本文\n", config)
        assert result.html.startswith("<!DOCTYPE html>")
        # 外部参照ゼロ（閉域ネットワークでは CDN に出られない）。
        assert "http://" not in result.html and "https://" not in result.html
        assert "<style>" in result.html

    def test_title_from_front_matter(self, config):
        result = convert_text("---\ntitle: 定例会\n---\n\n# 別の見出し\n", config)
        assert result.title == "定例会"

    def test_title_falls_back_to_first_heading(self, config):
        assert convert_text("# 最初の見出し\n\n本文\n", config).title == "最初の見出し"

    def test_title_falls_back_to_filename(self, config, tmp_path: Path):
        result = convert_text("本文だけ\n", config, source_path=tmp_path / "メモ.md")
        assert result.title == "メモ"

    def test_meta_header_rows(self, config):
        source = "---\ntype: minutes\n日時: 2026-09-14\n場所: 第2会議室\n---\n\n## 議題\n"
        html = convert_text(source, config).html
        assert "日時" in html and "第2会議室" in html

    def test_meta_header_skips_empty_keys(self, config):
        """meta_header に並んでいても、front matter に値が無ければ行を出さない。"""
        html = convert_text("---\ntype: minutes\n日時: 2026-09-14\n---\n\n## 議題\n", config).html
        assert "<th scope=\"row\">場所</th>" not in html

    def test_content_is_not_escaped(self, config):
        html = convert_text("**強調**\n", config).html
        assert "<strong>強調</strong>" in html

    def test_tables_extension_is_on(self, config):
        html = convert_text("| A | B |\n| --- | --- |\n| 1 | 2 |\n", config).html
        assert "<table>" in html or "<table " in html

    def test_profile_name_is_reported(self, config):
        assert convert_text("---\ntype: weekly\n---\n\n## 進捗\n", config).profile_name == "weekly"


class TestToc:
    def test_toc_off_for_default(self, config):
        assert 'class="dm-toc"' not in convert_text("# A\n\n## B\n", config).html

    def test_toc_on_for_minutes(self, config):
        html = convert_text("---\ntype: minutes\n---\n\n## 議題\n\n## 決定事項\n", config).html
        assert 'class="dm-toc"' in html and "議題" in html

    def test_japanese_anchor_is_kept(self, config):
        """既定の slugify は日本語を落として _1 になるため、unicode slug を使う。"""
        html = convert_text("---\ntype: minutes\n---\n\n## 議題\n", config).html
        assert 'href="#議題"' in html

    def test_numbering_for_spec(self, config):
        source = "---\ntype: spec\n---\n\n# 概要\n\n## 目的\n\n# 構成\n"
        html = convert_text(source, config).html
        assert "dm-heading__number" in html
        assert ">1.1<" in html  # 概要 > 目的
        assert ">2<" in html    # 構成

    def test_depth_limit(self, config):
        source = "---\ntype: spec\n---\n\n# A\n\n#### 深い見出し\n"
        html = convert_text(source, config).html
        toc = html[html.index('class="dm-toc"'):html.index("</nav>", html.index('class="dm-toc"'))]
        assert "深い見出し" not in toc


class TestGithubSlug:
    """見出しの id が GitHub と一致すること。

    期待値は github-slugger 2.0.0 の実測値。同じ .md を GitHub でも HTML でも
    読むため、文書内リンクが両方で成立する必要がある。
    """

    @pytest.mark.parametrize("heading, expected", [
        # 記号が消えて空白が隣り合う。GitHub は畳まないのでハイフン 2 つになる。
        ("常設の指示 — 利用するツールの共通指示欄に登録する",
         "常設の指示--利用するツールの共通指示欄に登録する"),
        ("Hello  World", "hello--world"),
        # 全角空白は半角空白ではないため、区切りにならず取り除かれる。
        ("A-6 世代管理　実装仕様書", "a-6-世代管理実装仕様書"),
        ("第1編 方式設計", "第1編-方式設計"),
        ("概要 (説明)", "概要-説明"),
        ("入力/出力の仕様", "入力出力の仕様"),
        ("設計方針・制約", "設計方針制約"),
        ("API の使い方", "api-の使い方"),
        ("1. はじめに", "1-はじめに"),
        ("ツール比較: docmold と pandoc", "ツール比較-docmold-と-pandoc"),
        ("用語（定義）", "用語定義"),
        ("Q&A", "qa"),
        # 長音符と繰り返し記号は文字として残す。
        ("サーバーの状態　々", "サーバーの状態々"),
    ])
    def test_matches_github(self, heading, expected):
        assert github_slug(heading) == expected

    def test_duplicate_headings_get_github_numbering(self, config):
        """同じ見出しが続いたときの番号も GitHub と同じ（``-1`` であって ``_1`` ではない）。"""
        source = "---\ntype: minutes\n---\n\n## 概要\n\n## 別の見出し\n\n## 概要\n"
        html = convert_text(source, config).html
        assert 'id="概要"' in html and 'id="概要-1"' in html
        assert "概要_1" not in html

    def test_numbering_does_not_leak_between_documents(self, config):
        """重複の数え直しは 1 文書の中だけ。次の文書で ``-1`` から始めない。"""
        source = "---\ntype: minutes\n---\n\n## 概要\n"
        assert 'id="概要"' in convert_text(source, config).html
        assert "概要-1" not in convert_text(source, config).html

    def test_heading_id_uses_the_rule(self, config):
        source = "---\ntype: minutes\n---\n\n## 常設の指示 — 登録する\n"
        html = convert_text(source, config).html
        assert 'id="常設の指示--登録する"' in html
        assert 'href="#常設の指示--登録する"' in html


class TestTocText:
    def test_step_number_is_not_duplicated(self, config):
        """step_numbering が差し込んだ番号を目次に出さない（「1手順 1:」にしない）。"""
        source = "---\ntype: procedure\n---\n\n## 手順 1: 事前確認\n\n内容\n"
        html = convert_text(source, config).html
        toc = html[html.index('class="dm-toc"'):html.index("</nav>", html.index('class="dm-toc"'))]
        assert "手順 1: 事前確認" in toc
        assert "1手順" not in toc

    def test_check_label_is_not_in_toc(self, config):
        source = "---\ntype: procedure\n---\n\n## 手順 1\n\n内容\n"
        html = convert_text(source, config).html
        toc = html[html.index('class="dm-toc"'):html.index("</nav>", html.index('class="dm-toc"'))]
        assert "完了" not in toc


class TestConvertFile:
    def test_reads_utf8(self, config, make_md):
        path = make_md("---\ntype: minutes\n---\n\n## 議題\n")
        assert convert_file(path, config).profile_name == "minutes"

    def test_reads_cp932(self, config, tmp_path: Path):
        """Windows で作られた .md は cp932 のことがある。"""
        path = tmp_path / "cp932.md"
        path.write_bytes("# 日本語の見出し\n".encode("cp932"))
        assert convert_file(path, config).title == "日本語の見出し"

    def test_missing_file(self, config, tmp_path: Path):
        with pytest.raises(ConversionError, match="読み込めません"):
            convert_file(tmp_path / "nope.md", config)


class TestImageEmbedding:
    def test_local_image_becomes_data_uri(self, config, tmp_path: Path):
        # 1x1 の GIF。
        image = tmp_path / "figure.gif"
        image.write_bytes(
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!"
            b"\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        path = tmp_path / "doc.md"
        path.write_text("![図](figure.gif)\n", encoding="utf-8")

        result = convert_file(path, config)
        assert "data:image/gif;base64," in result.html
        assert 'src="figure.gif"' not in result.html

    def test_missing_image_warns(self, config, make_md):
        result = convert_file(make_md("![図](nope.png)\n"), config)
        assert any("見つかりません" in w for w in result.warnings)

    def test_external_url_is_left_alone(self, config, make_md):
        result = convert_file(make_md("![図](https://example.com/a.png)\n"), config)
        assert "https://example.com/a.png" in result.html


class TestDocumentLinks:
    """文書間リンクは .html に向け直す（配布物のリンクが切れないように）。"""

    def _href(self, config, markdown_link: str) -> str:
        html = convert_text(markdown_link, config).html
        import re
        found = re.findall(r'<a href="([^"]+)"', html)
        return found[0] if found else ""

    def test_relative_md_becomes_html(self, config):
        assert self._href(config, "[設計書](設計書.md)\n") == "設計書.html"

    def test_subdirectory_is_kept(self, config):
        assert self._href(config, "[b](sub/b.md)\n") == "sub/b.html"

    def test_parent_directory_is_kept(self, config):
        assert self._href(config, "[a](../a.md)\n") == "../a.html"

    def test_markdown_extension(self, config):
        assert self._href(config, "[a](a.markdown)\n") == "a.html"

    def test_fragment_is_preserved(self, config):
        assert self._href(config, "[概要](設計書.md#概要)\n") == "設計書.html#概要"

    def test_query_is_preserved(self, config):
        assert self._href(config, "[a](a.md?v=2)\n") == "a.html?v=2"

    def test_external_url_is_untouched(self, config):
        assert self._href(config, "[外部](https://example.com/a.md)\n") == "https://example.com/a.md"

    def test_mailto_is_untouched(self, config):
        assert self._href(config, "[連絡](mailto:someone@example.com)\n") == "mailto:someone@example.com"

    def test_in_page_anchor_is_untouched(self, config):
        assert self._href(config, "[節へ](#概要)\n") == "#概要"

    def test_other_extension_is_untouched(self, config):
        assert self._href(config, "[資料](a.pdf)\n") == "a.pdf"

    def test_uppercase_extension(self, config):
        assert self._href(config, "[a](A.MD)\n") == "A.html"


class TestTitleFromHeading:
    def test_chapter_number_is_not_included(self, config):
        """spec は見出しに章番号を差し込むため、タイトルに混ざらないこと。"""
        result = convert_text("---\ntype: spec\n---\n\n# 概要\n\n本文\n", config)
        assert result.title == "概要"

    def test_step_number_is_not_included(self, config):
        result = convert_text("---\ntype: procedure\n---\n\n## 手順 1: 停止\n", config)
        assert result.title == "手順 1: 停止"

    def test_front_matter_title_still_wins(self, config):
        result = convert_text("---\ntype: spec\ntitle: 明示タイトル\n---\n\n# 概要\n", config)
        assert result.title == "明示タイトル"


class TestMetaTypos:
    """front matter のキーの打ち間違いを指摘する。

    未知のキーを一律に警告すると、覚え書きとして自由に書いた項目まで指摘してしまう。
    「意味を持つキーによく似ているのに一致しない」ものだけを対象にする。
    """

    def _warnings(self, config, front_matter: str) -> list:
        return convert_text(f"---\n{front_matter}---\n\n## 議題\n", config).warnings

    def test_misspelled_title(self, config):
        warnings = self._warnings(config, "type: minutes\ntitel: 打ち間違い\n")
        assert any("'titel'" in w and "'title'" in w for w in warnings)

    def test_misspelled_type(self, config):
        assert any("'type'" in w for w in self._warnings(config, "tyep: minutes\n"))

    def test_correct_keys_are_silent(self, config):
        assert self._warnings(config, "type: minutes\ntitle: 正\n日時: 2026-09-16\n") == []

    def test_free_form_key_is_not_flagged(self, config):
        """覚え書きの項目は指摘しない。"""
        assert self._warnings(config, "type: minutes\n備考: 自由に書いた項目\n") == []

    def test_similar_key_already_present_is_not_flagged(self, config):
        """作成日と作成者のように書き分けている場合は指摘しない。"""
        source = "type: spec\n作成日: 2026-09-16\n作成者: 鈴木花子\n"
        assert self._warnings(config, source) == []

    def test_internal_keys_are_ignored(self, config):
        assert self._warnings(config, "type: minutes\n_derived: x\n") == []

    def test_meta_header_keys_are_known(self, config):
        """プロファイルの meta_header に並べたキーは既知として扱う。"""
        assert self._warnings(config, "type: incident\n発生日時: 2026-09-16\n") == []

    def test_strict_turns_it_into_a_failure(self, config):
        """--strict なら取りこぼさない（cli 側の挙動は test_cli で検証）。"""
        assert len(self._warnings(config, "type: minutes\ntitel: 打ち間違い\n")) == 1


class TestLinkSchemes:
    """本文に書いた file: のリンクを、種類ごとに通すか落とすか。"""

    BODY = ("## トピックス\n\n### x\n\n- [手順書](file:///C:/docs/a.xlsx)\n\n"
            "## 前週\n\n### バグ\n\n本文\n\n## 今週\n\n### バグ\n\n本文\n"
            "\n## 来週\n\n### バグ\n\n本文\n")

    def test_weekly3_keeps_file_links(self, config):
        result = convert_text(f"---\ntype: weekly3\ntitle: t\n---\n\n{self.BODY}", config)
        assert 'href="file:///C:/docs/a.xlsx"' in result.html
        assert result.warnings == []

    def test_other_types_drop_file_links(self, config):
        result = convert_text(
            "---\ntype: minutes\ntitle: t\n---\n\n## x\n\n- [手順書](file:///C:/docs/a.xlsx)\n",
            config,
        )
        assert "file:///C:/docs/a.xlsx" not in result.html
        assert "本文の HTML を 1 箇所" in result.warnings[0]
