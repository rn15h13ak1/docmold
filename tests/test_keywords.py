"""keywords: ルールの検出語を config.yaml から差し替えられること。

表記ゆれ（「参加メンバー」「進捗状況」など）への対応で、コードを直さずに
設定ファイルだけで済ませられるようにするための仕組み。
"""
from __future__ import annotations

import pytest

from config import ConfigError, build_config
from converter import convert_text
from rules import keywords


@pytest.fixture(autouse=True)
def restore_defaults():
    """検出語はモジュール状態なので、テストごとに既定へ戻す。"""
    yield
    keywords.reset()


class TestRegistry:
    def test_defaults_are_available(self):
        assert "出席者" in keywords.get("attendee")

    def test_override_replaces_the_group(self):
        keywords.use({"attendee": ["参加メンバー"]})
        assert keywords.get("attendee") == ["参加メンバー"]

    def test_other_groups_keep_defaults(self):
        keywords.use({"attendee": ["参加メンバー"]})
        assert "todo" in keywords.get("todo")

    def test_reset_restores_defaults(self):
        keywords.use({"attendee": ["参加メンバー"]})
        keywords.reset()
        assert "出席者" in keywords.get("attendee")

    def test_unknown_group_raises(self):
        with pytest.raises(KeyError, match="未知のキーワードグループ"):
            keywords.get("attendees")

    def test_unknown_groups_are_detected(self):
        assert keywords.unknown_groups(["attendee", "nope"]) == {"nope"}


class TestConfigValidation:
    def _build(self, keyword_section: dict):
        return build_config({
            "profiles": {"default": {}},
            "themes": {"corporate": {"accent": "#000"}},
            "keywords": keyword_section,
        })

    def test_valid_group(self):
        config = self._build({"status_column": ["状態", "進捗状況"]})
        assert config.keywords["status_column"] == ["状態", "進捗状況"]

    def test_unknown_group_is_rejected(self):
        with pytest.raises(ConfigError, match="未知のグループ"):
            self._build({"attendees": ["x"]})

    def test_empty_list_is_rejected(self):
        """空にすると検出できなくなるため、事故を防ぐ。"""
        with pytest.raises(ConfigError, match="空にはできません"):
            self._build({"attendee": []})

    def test_string_becomes_single_item_list(self):
        assert self._build({"attendee": "参加メンバー"}).keywords["attendee"] == ["参加メンバー"]


class TestAppliedToConversion:
    def _config(self, keyword_section: dict = None):
        return build_config({
            "profiles": {
                "default": {},
                "weekly": {"template": "dashboard.html", "rules": ["status_badge"]},
                "minutes": {"rules": ["attendee_table"]},
            },
            "themes": {"corporate": {"accent": "#000"}},
            "keywords": keyword_section or {},
        })

    def _body(self, html: str) -> str:
        return html[html.index("<main"):html.index("</main>")]

    def test_default_does_not_match_variant(self):
        source = ("---\ntype: weekly\n---\n\n"
                  "| 作業 | 進捗状況 |\n| --- | --- |\n| A | 完了 |\n")
        body = self._body(convert_text(source, self._config()).html)
        assert "dm-badge" not in body

    def test_override_makes_it_match(self):
        source = ("---\ntype: weekly\n---\n\n"
                  "| 作業 | 進捗状況 |\n| --- | --- |\n| A | 完了 |\n")
        config = self._config({"status_column": ["状態", "進捗状況"]})
        body = self._body(convert_text(source, config).html)
        assert "dm-badge--ok" in body

    def test_attendee_heading_variant(self):
        source = "---\ntype: minutes\n---\n\n## 出席メンバー\n\n- 山田太郎\n"
        assert "dm-attendees" not in self._body(convert_text(source, self._config()).html)

        config = self._config({"attendee": ["出席メンバー"]})
        assert "dm-attendees" in self._body(convert_text(source, config).html)

    def test_status_words_can_be_retuned(self):
        """自社の言い回し（「対応完了」など）を ok 判定に足せる。"""
        source = ("---\ntype: weekly\n---\n\n"
                  "| 作業 | 状態 |\n| --- | --- |\n| A | 検収済 |\n")
        config = self._config({"status_ok": ["検収済"]})
        assert "dm-badge--ok" in self._body(convert_text(source, config).html)

    def test_each_conversion_applies_its_own_config(self):
        """設定の違う Config で続けて変換しても、前の設定が残らない。"""
        source = ("---\ntype: weekly\n---\n\n"
                  "| 作業 | 進捗状況 |\n| --- | --- |\n| A | 完了 |\n")
        convert_text(source, self._config({"status_column": ["進捗状況"]}))
        body = self._body(convert_text(source, self._config()).html)
        assert "dm-badge" not in body


class TestConfigExample:
    def test_every_group_is_listed_in_the_example(self):
        """config.example.yaml の既定値一覧が、グループの増減に追随しているか。"""
        from pathlib import Path

        from rules.keywords import DEFAULTS

        text = Path("config.example.yaml").read_text(encoding="utf-8")
        missing = [name for name in DEFAULTS if f"#   {name}: [" not in text]
        assert missing == []

    def test_listed_words_match_the_defaults(self):
        from pathlib import Path

        from rules.keywords import DEFAULTS

        text = Path("config.example.yaml").read_text(encoding="utf-8")
        for name, words in DEFAULTS.items():
            assert f"#   {name}: [{', '.join(words)}]" in text
