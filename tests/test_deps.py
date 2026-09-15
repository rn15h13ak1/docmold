"""deps: 依存が足りないときの案内。

インタプリタを取り違えて起動されたときに、トレースバックではなく
対処を出せること（そのために deps 自体はサードパーティを import しない）。
"""
from __future__ import annotations

import sys

import pytest

import deps


class TestMissing:
    def test_nothing_missing_in_this_environment(self):
        """テストが動いている以上、必須パッケージは揃っているはず。"""
        assert deps.missing() == []

    def test_reports_package_name_not_module_name(self, monkeypatch):
        """案内には pip で使う名前を出す（bs4 ではなく beautifulsoup4）。"""
        monkeypatch.setattr(deps.importlib.util, "find_spec", lambda name: None)
        assert "beautifulsoup4" in deps.missing()
        assert "bs4" not in deps.missing()

    def test_optional_packages_are_not_required(self):
        """Pygments が無くても変換自体は通るため、必須に含めない。"""
        assert "pygments" not in deps.REQUIRED
        assert "pygments" in deps.OPTIONAL


class TestExplain:
    def test_names_the_running_interpreter(self):
        """どの Python で動いているかが分かること（取り違えの原因がこれのため）。"""
        assert sys.executable in deps.explain(["Markdown"])

    def test_gives_an_install_command(self):
        message = deps.explain(["Markdown"])
        assert "-m pip install -r" in message
        assert "requirements.txt" in message

    def test_lists_the_missing_packages(self):
        assert "Markdown, Jinja2" in deps.explain(["Markdown", "Jinja2"])


class TestEnsure:
    def test_passes_when_everything_is_present(self):
        deps.ensure()

    def test_exits_with_guidance_when_missing(self, monkeypatch, capsys):
        monkeypatch.setattr(deps, "missing", lambda: ["Markdown"])
        with pytest.raises(SystemExit) as exit_info:
            deps.ensure()
        assert exit_info.value.code == 2
        assert "必要なライブラリが入っていません" in capsys.readouterr().err

    def test_imports_no_third_party(self):
        """deps 自身が依存を import していたら案内を出す前に落ちてしまう。"""
        source = (deps.SCRIPT_DIR / "deps.py").read_text(encoding="utf-8")
        for module in ("markdown", "jinja2", "yaml", "bs4", "pygments"):
            assert f"import {module}" not in source
