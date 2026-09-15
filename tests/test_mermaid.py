"""mermaid: 図の取り込みと、mermaid.js の入手先。

図は既定で無効。有効にすると、CDN 参照（HTML は軽いが閲覧時にインターネットが要る）か
同梱の埋め込み（外部参照ゼロだがファイルが大きい）かを選べる。
"""
from __future__ import annotations

import pytest

from config import DEFAULT_MERMAID_URL, ConfigError, MermaidSettings, build_config
from converter import convert_text

DIAGRAM = "```mermaid\ngraph TD\n  A[受付] --> B[審査]\n```\n"


def config_with(mermaid) -> object:
    return build_config({
        "profiles": {"default": {}, "spec": {"mermaid": mermaid}},
        "themes": {"corporate": {"accent": "#000"}},
    })


def convert(mermaid, source: str = DIAGRAM) -> str:
    return convert_text(f"---\ntype: spec\n---\n\n{source}", config_with(mermaid)).html


class TestSettings:
    @pytest.mark.parametrize("value", [None, False])
    def test_disabled_by_default(self, value):
        assert MermaidSettings.parse(value, "profiles.spec").enabled is False

    def test_true_means_bundled(self):
        settings = MermaidSettings.parse(True, "profiles.spec")
        assert (settings.enabled, settings.bundled) == (True, True)

    def test_cdn_uses_the_default_url(self):
        settings = MermaidSettings.parse("cdn", "profiles.spec")
        assert (settings.enabled, settings.bundled, settings.url) == (True, False, DEFAULT_MERMAID_URL)

    def test_explicit_url(self):
        settings = MermaidSettings.parse("https://example.com/m.js", "profiles.spec")
        assert settings.url == "https://example.com/m.js"

    def test_mapping_with_integrity(self):
        settings = MermaidSettings.parse(
            {"url": "https://example.com/m.js", "integrity": "sha384-x"}, "profiles.spec")
        assert settings.integrity == "sha384-x"

    def test_unknown_keyword_is_rejected(self):
        with pytest.raises(ConfigError, match="bundled"):
            MermaidSettings.parse("internet", "profiles.spec")

    def test_non_http_url_is_rejected(self):
        with pytest.raises(ConfigError, match="http"):
            MermaidSettings.parse({"url": "file:///m.js"}, "profiles.spec")

    def test_bundled_with_url_is_rejected(self):
        with pytest.raises(ConfigError, match="url は指定できません"):
            MermaidSettings.parse({"source": "bundled", "url": "https://x/m.js"}, "profiles.spec")


class TestDiagramMarkup:
    def test_fence_becomes_a_mermaid_element(self):
        assert '<pre class="mermaid">' in convert("cdn")

    def test_definition_is_kept_verbatim(self):
        assert "graph TD" in convert("cdn")

    def test_angle_brackets_are_escaped(self):
        """A --> B[<判定>] が HTML として解釈されないこと。"""
        html = convert("cdn", "```mermaid\ngraph TD\n  A --> B[<判定>]\n```\n")
        assert "&lt;判定&gt;" in html
        assert "<判定>" not in html

    def test_attribute_form_is_accepted(self):
        html = convert("cdn", "``` { .mermaid }\ngraph TD\n  A --> B\n```\n")
        assert '<pre class="mermaid">' in html

    def test_other_languages_still_highlighted(self):
        html = convert("cdn", "```bash\nls -l\n```\n")
        assert "codehilite" in html
        assert '<pre class="mermaid">' not in html

    def test_not_transformed_when_disabled(self):
        html = convert(False)
        assert '<pre class="mermaid">' not in html
        assert "codehilite" in html

    def test_unclosed_fence_is_left_to_markdown(self):
        html = convert("cdn", "```mermaid\ngraph TD\n")
        assert '<pre class="mermaid">' not in html


class TestScriptTag:
    def test_cdn_is_referenced(self):
        assert f'<script src="{DEFAULT_MERMAID_URL}"></script>' in convert("cdn")

    def test_integrity_adds_crossorigin(self):
        html = convert({"url": "https://example.com/m.js", "integrity": "sha384-x"})
        assert 'integrity="sha384-x"' in html and 'crossorigin="anonymous"' in html

    def test_initialize_is_called(self):
        assert "mermaid.initialize" in convert("cdn")

    def test_nothing_when_disabled(self):
        html = convert(False)
        assert "mermaid.initialize" not in html
        assert "mermaid.min.js" not in html

    def test_disabled_output_stays_self_contained(self):
        """既定のままなら外部参照は入らない。"""
        import re
        html = convert(False)
        assert not re.search(r'src\s*=\s*["\']https?://', html)
