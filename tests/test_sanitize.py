"""sanitize: 本文の生 HTML を許可リストで絞る。

出力はファイルサーバやメールで配布されるため、他の人が書いた .md に紛れた
script などをそのまま配らないようにする。Markdown 本来の記法と、
Markdown 自身が生成する属性（表の桁揃えなど）は壊さないこと。
"""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from config import ConfigError, build_config, parse_sanitize
from converter import convert_text
from sanitize import sanitize


def clean(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    sanitize(soup)
    return str(soup)


def config_with(sanitize_value=None, profile_value=None):
    raw = {
        "profiles": {"default": {}, "spec": {}},
        "themes": {"corporate": {"accent": "#000"}},
    }
    if sanitize_value is not None:
        raw["sanitize"] = sanitize_value
    if profile_value is not None:
        raw["profiles"]["spec"]["sanitize"] = profile_value
    return build_config(raw)


def body(html: str) -> str:
    return html[html.index("<main"):html.index("</main>")]


class TestDangerousMarkup:
    def test_script_is_removed_with_content(self):
        assert "alert" not in clean("<p>本文</p><script>alert(1)</script>")

    def test_event_handler_is_removed(self):
        result = clean('<img src="図.png" alt="構成" onerror="alert(1)">')
        assert "onerror" not in result
        assert 'src="図.png"' in result and 'alt="構成"' in result

    def test_javascript_href_is_removed(self):
        result = clean('<a href="javascript:alert(1)">押す</a>')
        assert "javascript:" not in result
        assert "押す" in result  # 文字は残す

    def test_iframe_is_removed(self):
        assert "iframe" not in clean('<iframe src="https://example.com"></iframe>')

    def test_form_controls_are_removed(self):
        assert "input" not in clean('<form><input name="x"></form>')

    def test_inline_svg_is_removed(self):
        assert "svg" not in clean('<svg><script>alert(1)</script></svg>')

    def test_unknown_tag_keeps_its_text(self):
        """許可していないだけの要素は、中身を残して外す。"""
        result = clean("<font color='red'>赤い字</font>")
        assert "font" not in result and "赤い字" in result

    def test_style_attribute_is_dropped(self):
        assert "color" not in clean('<div style="color:red">注意</div>')

    def test_removed_count_is_reported(self):
        soup = BeautifulSoup('<script>x</script><img onerror="y">', "html.parser")
        assert sanitize(soup) >= 2


class TestHarmlessMarkup:
    @pytest.mark.parametrize("html", [
        "<p>1行目<br/>2行目</p>",
        "<details><summary>補足</summary><p>中身</p></details>",
        "<p><strong>強調</strong> と <code>コード</code></p>",
        '<p><abbr title="Application">AP</abbr></p>',
        "<blockquote><p>引用</p></blockquote>",
        '<p><sup id="fnref:1"><a class="footnote-ref" href="#fn:1">1</a></sup></p>',
    ])
    def test_kept_as_is(self, html):
        assert clean(html) == html

    def test_table_alignment_survives(self):
        """Markdown は桁揃えを style で出すため、この形だけは通す。"""
        html = '<table><tr><th style="text-align: right;">右</th></tr></table>'
        assert 'style="text-align: right;"' in clean(html)

    def test_other_style_on_cell_is_dropped(self):
        html = '<table><tr><td style="display:none">隠す</td></tr></table>'
        assert "display" not in clean(html)

    def test_colspan_is_kept(self):
        assert 'colspan="2"' in clean('<table><tr><td colspan="2">A</td></tr></table>')

    def test_relative_link_is_kept(self):
        assert 'href="設計書.md"' in clean('<a href="設計書.md">リンク</a>')

    def test_external_link_is_kept(self):
        assert 'href="https://example.com"' in clean('<a href="https://example.com">外部</a>')

    def test_embedded_image_is_kept(self):
        """画像の埋め込みに使う data URI は通す。"""
        html = '<img src="data:image/png;base64,iVBORw0KGgo=" alt="図">'
        assert "data:image/png" in clean(html)

    def test_non_image_data_uri_is_dropped(self):
        html = '<img src="data:text/html;base64,PHNjcmlwdD4=" alt="x">'
        assert "data:text/html" not in clean(html)


class TestProfileSettings:
    def test_default_is_strict(self):
        assert config_with().profile("default").sanitize == "strict"

    def test_top_level_default_applies_to_every_profile(self):
        config = config_with(sanitize_value=False)
        assert config.profile("default").sanitize == "none"
        assert config.profile("spec").sanitize == "none"

    def test_profile_overrides_the_default(self):
        config = config_with(sanitize_value="strict", profile_value=False)
        assert config.profile("default").sanitize == "strict"
        assert config.profile("spec").sanitize == "none"

    def test_profile_can_turn_it_on_when_default_is_off(self):
        config = config_with(sanitize_value=False, profile_value="strict")
        assert config.profile("spec").sanitize == "strict"

    @pytest.mark.parametrize("value,expected", [
        (True, "strict"), (False, "none"), ("strict", "strict"), ("none", "none"), (None, "strict"),
    ])
    def test_accepted_values(self, value, expected):
        assert parse_sanitize(value, "profiles.spec") == expected

    def test_unknown_value_is_rejected(self):
        with pytest.raises(ConfigError, match="sanitize"):
            parse_sanitize("kibishime", "profiles.spec")


class TestConversion:
    def test_script_does_not_reach_the_output(self):
        html = convert_text("<script>alert(1)</script>\n\n本文\n", config_with()).html
        assert "alert(1)" not in body(html)

    def test_disabled_lets_it_through(self):
        html = convert_text("<script>alert(1)</script>\n", config_with(sanitize_value=False)).html
        assert "alert(1)" in body(html)

    def test_warning_tells_how_to_disable(self):
        result = convert_text("<script>alert(1)</script>\n", config_with())
        assert any("sanitize" in w for w in result.warnings)

    def test_no_warning_for_plain_markdown(self):
        result = convert_text("# 見出し\n\n**強調**\n", config_with())
        assert result.warnings == []

    def test_generated_markup_is_not_filtered(self):
        """ルールが作るチェックボックスはサニタイズの後に組み立てる。"""
        config = build_config({
            "profiles": {"default": {}, "minutes": {"rules": ["todo_checklist"]}},
            "themes": {"corporate": {"accent": "#000"}},
        })
        html = convert_text("---\ntype: minutes\n---\n\n## ToDo\n\n- [ ] 作業\n", config).html
        assert '<input class="dm-check"' in body(html)

    def test_document_links_still_rewritten(self):
        html = convert_text("[設計書](設計書.md)\n", config_with()).html
        assert 'href="設計書.html"' in body(html)
