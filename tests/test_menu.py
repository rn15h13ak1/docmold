"""menu: 対話メニューの入力検証・引数の組み立て・前回値の記憶。

本体を実行せずに検証する。対話ループ本体 (main) は副作用が大きいため対象外。
"""
from __future__ import annotations

from pathlib import Path

import pytest

import menu


class TestInputValidation:
    def test_markdown_file_is_accepted(self, make_md):
        assert menu.is_convertible(str(make_md("# A\n"))) is True

    def test_markdown_extension_variant(self, make_md):
        assert menu.is_convertible(str(make_md("# A\n", "doc.markdown"))) is True

    def test_other_extension_is_rejected(self, tmp_path: Path):
        path = tmp_path / "note.txt"
        path.write_text("text\n", encoding="utf-8")
        assert menu.is_convertible(str(path)) is False

    def test_directory_with_markdown_is_accepted(self, make_md):
        path = make_md("# A\n", "docs/a.md")
        assert menu.is_convertible(str(path.parent)) is True

    def test_directory_without_markdown_is_rejected(self, tmp_path: Path):
        (tmp_path / "empty").mkdir()
        assert menu.is_convertible(str(tmp_path / "empty")) is False

    def test_missing_path_is_rejected(self, tmp_path: Path):
        assert menu.is_convertible(str(tmp_path / "nope.md")) is False

    def test_quoted_path_is_accepted(self, make_md):
        """Windows のドラッグ＆ドロップで付く引用符を落とす。"""
        path = make_md("# A\n")
        assert menu.is_convertible(f'"{path}"') is True


class TestDescribeInput:
    def test_file_count_for_directory(self, make_md):
        make_md("# A\n", "docs/a.md")
        make_md("# B\n", "docs/sub/b.md")
        directory = make_md("# C\n", "docs/c.md").parent
        assert "3 ファイル" in menu.describe_input(str(directory))

    def test_single_file(self, make_md):
        assert "1 ファイル" in menu.describe_input(str(make_md("# A\n")))

    def test_missing_path(self, tmp_path: Path):
        assert "見つかりません" in menu.describe_input(str(tmp_path / "nope.md"))


class TestBuildArgs:
    def test_minimal(self):
        assert menu.build_args("docs") == ["docs", "--verbose"]

    def test_output_and_index(self):
        args = menu.build_args("docs", output="out", index=True)
        assert args[:1] == ["docs"]
        assert "-o" in args and "out" in args
        assert "--index" in args

    def test_type_override(self):
        assert "--type" in menu.build_args("a.md", type_override="incident")

    def test_no_type_flag_when_following_front_matter(self):
        """「front matter に従う」を選んだときは --type を渡さない。"""
        assert "--type" not in menu.build_args("a.md", type_override="")

    def test_dry_run(self):
        assert "--dry-run" in menu.build_args("docs", dry_run=True)

    def test_no_dry_run_flag_by_default(self):
        assert "--dry-run" not in menu.build_args("docs")

    def test_config_is_passed_through(self):
        args = menu.build_args("docs", config_path="my.yaml")
        assert args[args.index("--config") + 1] == "my.yaml"

    def test_index_is_omitted_when_false(self):
        assert "--index" not in menu.build_args("docs", index=False)


class TestHistory:
    def test_roundtrip(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(menu, "HISTORY_PATH", tmp_path / "history.json")
        menu.save_history({"input": "docs", "output": "out"})
        assert menu.load_history()["input"] == "docs"

    def test_broken_file_falls_back_to_empty(self, tmp_path: Path, monkeypatch):
        path = tmp_path / "history.json"
        path.write_text("{壊れた", encoding="utf-8")
        monkeypatch.setattr(menu, "HISTORY_PATH", path)
        assert menu.load_history() == {}

    def test_missing_file_falls_back_to_empty(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(menu, "HISTORY_PATH", tmp_path / "nope.json")
        assert menu.load_history() == {}

    def test_unwritable_path_does_not_raise(self, tmp_path: Path, monkeypatch):
        """保存できなくても実行は妨げない。"""
        monkeypatch.setattr(menu, "HISTORY_PATH", tmp_path / "nodir" / "history.json")
        menu.save_history({"input": "docs"})


class TestChooseType:
    def test_front_matter_is_the_first_choice(self, config, monkeypatch):
        monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: 1)
        assert menu.choose_type(config) == ""

    def test_named_type_is_returned(self, config, monkeypatch):
        # 2 番目以降が種類。type_names の順に並ぶ。
        index = config.type_names.index("incident") + 2
        monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: index)
        assert menu.choose_type(config) == "incident"

    def test_back_returns_none(self, config, monkeypatch):
        monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: 0)
        assert menu.choose_type(config) is None


class TestInputText:
    def test_default_on_empty_enter(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert menu.input_text("パス", default="out") == "out"

    def test_none_when_no_default(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert menu.input_text("パス") is None

    def test_rejects_until_valid(self, monkeypatch):
        answers = iter(["だめ", "よい"])
        monkeypatch.setattr("builtins.input", lambda _: next(answers))
        assert menu.input_text("値", validate=lambda v: v == "よい", hint="") == "よい"


class TestConfirm:
    @pytest.mark.parametrize("answer,expected", [
        ("", True), ("y", True), ("yes", True), ("n", False), ("no", False),
    ])
    def test_answers(self, monkeypatch, answer, expected):
        monkeypatch.setattr("builtins.input", lambda _: answer)
        assert menu.confirm("よいですか？", default_yes=True) is expected

    def test_empty_uses_default_no(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert menu.confirm("よいですか？", default_yes=False) is False


class TestPrintMenu:
    def test_returns_choice(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "2")
        assert menu.print_menu("t", ["a", "b"]) == 2

    def test_zero_is_back(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "0")
        assert menu.print_menu("t", ["a", "b"]) == 0

    def test_empty_uses_default(self, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert menu.print_menu("t", ["a", "b"], default=2) == 2

    def test_out_of_range_is_rejected(self, monkeypatch, capsys):
        answers = iter(["9", "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(answers))
        assert menu.print_menu("t", ["a", "b"]) == 1
        assert "無効な入力" in capsys.readouterr().out


class TestCollectInputs:
    def test_cancel_at_path_returns_none(self, config, monkeypatch):
        monkeypatch.setattr(menu, "input_text", lambda *a, **kw: None)
        assert menu.collect_inputs(config, {}) is None

    def test_index_is_not_asked_for_single_file(self, config, monkeypatch, make_md):
        path = str(make_md("# A\n"))
        monkeypatch.setattr(menu, "input_text", lambda *a, **kw: path)
        monkeypatch.setattr(menu, "choose_type", lambda _: "")
        monkeypatch.setattr(menu, "choose_output", lambda _: "")
        monkeypatch.setattr(menu, "confirm",
                            lambda *a, **kw: pytest.fail("単一ファイルで索引を尋ねた"))
        assert menu.collect_inputs(config, {})["index"] is False

    def test_index_is_asked_for_directory(self, config, monkeypatch, make_md):
        directory = str(make_md("# A\n", "docs/a.md").parent)
        monkeypatch.setattr(menu, "input_text", lambda *a, **kw: directory)
        monkeypatch.setattr(menu, "choose_type", lambda _: "")
        monkeypatch.setattr(menu, "choose_output", lambda _: "")
        monkeypatch.setattr(menu, "confirm", lambda *a, **kw: True)
        assert menu.collect_inputs(config, {})["index"] is True


class TestChooseOutput:
    def test_default_returns_empty_so_no_o_flag(self, monkeypatch):
        """既定を選んだら -o を渡さない（本体のタイムスタンプ付き out/ に任せる）。"""
        monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: 1)
        assert menu.choose_output({}) == ""
        assert "-o" not in menu.build_args("docs", output="")

    def test_explicit_path(self, monkeypatch):
        monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: 2)
        monkeypatch.setattr(menu, "input_text", lambda *a, **kw: "//server/share/html")
        assert menu.choose_output({}) == "//server/share/html"

    def test_back_returns_none(self, monkeypatch):
        monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: 0)
        assert menu.choose_output({}) is None


class TestLatestOutput:
    def test_newest_run_folder_is_picked(self, tmp_path, monkeypatch):
        base = tmp_path / "out"
        for name in ("20260914-100000", "20260914-120000", "20260913-235959"):
            (base / name).mkdir(parents=True)
        monkeypatch.setattr(menu.docmold_cli, "DEFAULT_OUTPUT_DIR", base)
        assert menu.latest_output("").name == "20260914-120000"

    def test_none_when_nothing_was_written(self, tmp_path, monkeypatch):
        monkeypatch.setattr(menu.docmold_cli, "DEFAULT_OUTPUT_DIR", tmp_path / "nope")
        assert menu.latest_output("") is None

    def test_explicit_directory_is_used_as_is(self, tmp_path, monkeypatch):
        assert menu.latest_output(str(tmp_path)) == tmp_path


class TestRunConvert:
    def test_cancel_does_not_run(self, config, monkeypatch):
        monkeypatch.setattr(menu, "collect_inputs", lambda *a: None)
        monkeypatch.setattr(menu, "run_docmold",
                            lambda *a: pytest.fail("キャンセル時に実行された"))
        assert menu.run_convert(config, "", {}) is None

    def test_cancel_at_mode_does_not_run(self, config, monkeypatch):
        monkeypatch.setattr(menu, "collect_inputs",
                            lambda *a: {"input": "docs", "type": "", "output": "out", "index": False})
        monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: 0)
        monkeypatch.setattr(menu, "run_docmold",
                            lambda *a: pytest.fail("キャンセル時に実行された"))
        assert menu.run_convert(config, "", {}) is None

    def test_history_is_saved_before_running(self, config, monkeypatch, tmp_path: Path):
        monkeypatch.setattr(menu, "HISTORY_PATH", tmp_path / "history.json")
        monkeypatch.setattr(menu, "collect_inputs",
                            lambda *a: {"input": "docs", "type": "spec",
                                        "output": "", "index": True})
        monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: 2)  # 検証のみ
        recorded = {}

        def fake_run(args):
            recorded["args"] = args
            return 0

        monkeypatch.setattr(menu, "run_docmold", fake_run)

        history = {}
        assert menu.run_convert(config, "", history) == 0
        assert history["input"] == "docs"
        assert menu.load_history()["type"] == "spec"
        assert "--dry-run" in recorded["args"]

    def test_dry_run_does_not_offer_to_open_output(self, config, monkeypatch, tmp_path: Path):
        monkeypatch.setattr(menu, "HISTORY_PATH", tmp_path / "history.json")
        monkeypatch.setattr(menu, "collect_inputs",
                            lambda *a: {"input": "docs", "type": "",
                                        "output": str(tmp_path), "index": False})
        monkeypatch.setattr(menu, "print_menu", lambda *a, **kw: 2)  # 検証のみ
        monkeypatch.setattr(menu, "run_docmold", lambda args: 0)
        monkeypatch.setattr(menu, "confirm",
                            lambda *a, **kw: pytest.fail("検証のみで出力先を開こうとした"))
        assert menu.run_convert(config, "", {}) == 0


class TestParser:
    def test_config_defaults_to_empty(self):
        assert menu.build_parser().parse_args([]).config == ""

    def test_config_is_parsed(self):
        assert menu.build_parser().parse_args(["--config", "my.yaml"]).config == "my.yaml"


class TestDescribeConfig:
    def test_reports_profile_count(self):
        assert "6 種類" in menu.describe_config("")

    def test_broken_config_is_reported(self, make_config):
        cfg = make_config("profiles:\n  default:\n    theme: nope\n")
        assert menu.describe_config(str(cfg)).startswith("※")
