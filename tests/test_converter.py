"""converter: 種類の判定と変換パイプライン。"""
from __future__ import annotations

from pathlib import Path

import pytest

from converter import ConversionError, convert_file, convert_text, resolve_profile


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
