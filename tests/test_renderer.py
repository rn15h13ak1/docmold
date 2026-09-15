"""renderer: テンプレート描画とテーマ CSS の埋め込み。"""
from __future__ import annotations

import pytest

from config import build_config
from converter import convert_text
from renderer import RenderError, build_css, get_environment, render


class TestCss:
    def test_theme_variables_are_emitted(self, config):
        css = build_css(config, config.profile("default"))
        assert "--accent: #00529b;" in css
        assert ":root {" in css

    def test_alert_theme_differs(self, config):
        corporate = build_css(config, config.profile("default"))
        alert = build_css(config, config.profile("incident"))
        assert corporate != alert
        assert "--accent: #c0392b;" in alert

    def test_print_css_is_included(self, config):
        assert "@media print" in build_css(config, config.profile("default"))

    def test_underscore_keys_become_hyphens(self, config):
        assert "--accent-weak:" in build_css(config, config.profile("default"))


class TestTemplates:
    def test_every_bundled_template_exists(self, config):
        environment = get_environment()
        for name in config.type_names:
            environment.get_template(config.profile(name).template)

    def test_missing_template_is_reported(self):
        config = build_config({
            "profiles": {"default": {"template": "nope.html"}},
            "themes": {"corporate": {"accent": "#000"}},
        })
        with pytest.raises(RenderError, match="テンプレートが見つかりません"):
            render(config=config, profile=config.profile("default"), content="",
                   title="t", meta={}, derived={}, toc=[], meta_header=[])


class TestOutput:
    def test_watermark_only_when_configured(self, config):
        assert 'class="dm-watermark"' in convert_text("---\ntype: incident\n---\n\n## 概要\n", config).html
        assert 'class="dm-watermark"' not in convert_text("## 概要\n", config).html

    def test_cover_page_only_for_spec(self, config):
        assert 'class="dm-cover"' in convert_text("---\ntype: spec\n---\n\n# 概要\n", config).html
        assert 'class="dm-cover"' not in convert_text("---\ntype: minutes\n---\n\n# 概要\n", config).html

    def test_print_break_class_for_procedure(self, config):
        html = convert_text("---\ntype: procedure\n---\n\n## 手順 1\n", config).html
        assert "dm-print-break-h2" in html

    def test_type_is_recorded_in_meta_tag(self, config):
        html = convert_text("---\ntype: weekly\n---\n\n## 進捗\n", config).html
        assert '<meta name="docmold-type" content="weekly">' in html

    def test_title_is_escaped(self, config):
        html = convert_text("---\ntitle: <script>x</script>\n---\n\n本文\n", config).html
        assert "<title><script>" not in html
        assert "&lt;script&gt;" in html

    def test_mermaid_warns_when_bundled_asset_missing(self, config):
        """同梱が無ければ黙って壊さず警告する（CDN からの自動取得はしない）。"""
        from config import MermaidSettings

        profile = config.profile("default")
        object.__setattr__(profile, "mermaid", MermaidSettings(enabled=True, bundled=True))
        warnings = []
        try:
            render(config=config, profile=profile, content="", title="t", meta={},
                   derived={}, toc=[], meta_header=[], warnings=warnings)
        finally:
            object.__setattr__(profile, "mermaid", MermaidSettings())
        assert any("mermaid" in w for w in warnings)

    def test_cdn_does_not_need_the_bundled_asset(self, config):
        from config import MermaidSettings

        profile = config.profile("default")
        object.__setattr__(profile, "mermaid",
                           MermaidSettings(enabled=True, bundled=False,
                                           url="https://example.com/mermaid.min.js"))
        warnings = []
        try:
            html = render(config=config, profile=profile, content="", title="t", meta={},
                          derived={}, toc=[], meta_header=[], warnings=warnings)
        finally:
            object.__setattr__(profile, "mermaid", MermaidSettings())
        assert 'src="https://example.com/mermaid.min.js"' in html
        assert warnings == []


class TestPrintPageNumbers:
    """印刷時のページ番号（記録として保管するときに参照しやすいように）。"""

    def test_page_counter_is_defined(self, config):
        css = build_css(config, config.profile("default"))
        assert "@bottom-center" in css
        assert 'counter(page) " / " counter(pages)' in css

    def test_cover_page_number_is_suppressed(self, config):
        """表紙のあるプロファイルでは 1 ページ目に番号を出さない。"""
        css = build_css(config, config.profile("spec"))
        assert "@page :first" in css

    def test_no_cover_rule_without_cover_page(self, config):
        assert "@page :first" not in build_css(config, config.profile("minutes"))

    def test_rule_is_inside_a_print_block(self, config):
        css = build_css(config, config.profile("spec"))
        assert css.index("@media print") < css.index("@bottom-center")
