"""config: プロファイル定義の読み込みと検証。"""
from __future__ import annotations

from pathlib import Path

import pytest

from config import ConfigError, build_config, load_config


class TestBundled:
    def test_bundled_profiles_load(self, config):
        assert "default" in config.profiles
        assert config.profile("minutes").rules
        assert config.profile("incident").theme == "alert"

    def test_type_names_sorted(self, config):
        assert config.type_names == sorted(config.type_names)

    def test_markdown_extensions_include_base(self, config):
        extensions = config.profile("default").markdown_extensions
        assert "extra" in extensions and "toc" in extensions


class TestUserOverride:
    def test_partial_override_keeps_rest(self, make_config):
        cfg = make_config("""
profiles:
  incident:
    watermark: false
""")
        config = load_config(str(cfg))
        incident = config.profile("incident")
        assert incident.watermark is None
        # 上書きしていないキーは同梱の値が残る。
        assert incident.template == "report.html"
        assert incident.rules

    def test_add_new_type(self, make_config):
        cfg = make_config("""
profiles:
  review:
    description: レビュー記録
    template: article.html
    theme: corporate
    rules: [todo_checklist]
""")
        config = load_config(str(cfg))
        assert config.profile("review").description == "レビュー記録"

    def test_theme_variable_override(self, make_config):
        cfg = make_config("""
themes:
  corporate:
    accent: "#006c4b"
""")
        config = load_config(str(cfg))
        variables = config.themes["corporate"].variables
        assert variables["accent"] == "#006c4b"
        assert "font" in variables  # 他の変数は残る

    def test_missing_file(self, tmp_path: Path):
        with pytest.raises(ConfigError, match="見つかりません"):
            load_config(str(tmp_path / "nope.yaml"))


class TestValidation:
    def _build(self, profiles: dict, themes: dict = None):
        return build_config({
            "profiles": profiles,
            "themes": themes if themes is not None else {"corporate": {"accent": "#000"}},
        })

    def test_default_is_required(self):
        with pytest.raises(ConfigError, match="'default' が必要"):
            self._build({"minutes": {}})

    def test_unknown_profile_key(self):
        with pytest.raises(ConfigError, match="未知のキー"):
            self._build({"default": {"tempalte": "article.html"}})

    def test_unknown_theme(self):
        with pytest.raises(ConfigError, match="未定義のテーマ"):
            self._build({"default": {"theme": "nope"}})

    def test_unknown_rule(self):
        with pytest.raises(ConfigError, match="未登録のルール"):
            self._build({"default": {"rules": ["nope"]}})

    def test_unknown_top_level_key(self):
        with pytest.raises(ConfigError, match="未知のトップレベルキー"):
            build_config({"profiles": {"default": {}}, "profile": {}})

    def test_template_path_is_rejected(self):
        with pytest.raises(ConfigError, match="ファイル名で指定"):
            self._build({"default": {"template": "../etc/passwd"}})

    def test_toc_depth_range(self):
        with pytest.raises(ConfigError, match="1〜6"):
            self._build({"default": {"toc": {"depth": 9}}})


class TestTocSettings:
    def test_bool_forms(self, config):
        assert config.profile("minutes").toc.enabled is True
        assert config.profile("default").toc.enabled is False

    def test_mapping_form(self, config):
        toc = config.profile("spec").toc
        assert (toc.enabled, toc.depth, toc.numbering) == (True, 3, True)


class TestAllowSchemes:
    def test_default_is_empty(self, config):
        assert config.profile("minutes").allow_schemes == []

    def test_file_is_accepted(self, make_config):
        cfg = load_config(str(make_config(
            "profiles:\n  memo:\n    allow_schemes: [file]\n")))
        assert cfg.profile("memo").allow_schemes == ["file"]

    def test_trailing_colon_and_case_are_tolerated(self, make_config):
        cfg = load_config(str(make_config(
            "profiles:\n  memo:\n    allow_schemes: ['FILE:']\n")))
        assert cfg.profile("memo").allow_schemes == ["file"]

    def test_script_scheme_is_refused(self, make_config):
        with pytest.raises(ConfigError, match="通せません"):
            load_config(str(make_config(
                "profiles:\n  memo:\n    allow_schemes: [javascript]\n")))

    def test_string_is_refused(self, make_config):
        with pytest.raises(ConfigError, match="リストで指定"):
            load_config(str(make_config(
                "profiles:\n  memo:\n    allow_schemes: file\n")))
