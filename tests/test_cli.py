"""cli: 引数の解釈、入出力の解決、終了コード。"""
from __future__ import annotations

from pathlib import Path

import pytest

import cli
from cli import EXIT_CONFIG_ERROR, EXIT_FAILED, EXIT_OK, main


@pytest.fixture
def in_tmp(tmp_path: Path, monkeypatch):
    """CWD を一時ディレクトリにして、ユーザ config.yaml を拾わないようにする。

    既定の出力先はツール同梱の out/ に固定されているため、テストが本物の out/ を
    汚さないよう一時ディレクトリへ差し替える。
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "DEFAULT_OUTPUT_DIR", tmp_path / "tool-out")
    return tmp_path


def write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


class TestListing:
    def test_list_types(self, capsys, in_tmp):
        assert main(["--list-types"]) == EXIT_OK
        out = capsys.readouterr().out
        assert "minutes" in out and "incident" in out

    def test_list_rules(self, capsys, in_tmp):
        assert main(["--list-rules"]) == EXIT_OK
        assert "todo_checklist" in capsys.readouterr().out


class TestArguments:
    def test_no_input_is_an_error(self, in_tmp, capsys):
        assert main([]) == EXIT_CONFIG_ERROR
        assert "--list-types" in capsys.readouterr().err

    def test_unknown_type_override_is_rejected(self, in_tmp, capsys):
        write(in_tmp / "a.md", "# A\n")
        assert main(["a.md", "--type", "nope"]) == EXIT_CONFIG_ERROR
        assert "未定義" in capsys.readouterr().err

    def test_missing_input_is_reported(self, in_tmp, capsys):
        assert main(["nope.md"]) == EXIT_FAILED
        assert "見つかりません" in capsys.readouterr().err


class TestConversion:
    def test_single_file_default_output(self, in_tmp):
        """-o が無いときはツール同梱の out/<タイムスタンプ>/ に出す。"""
        write(in_tmp / "a.md", "# A\n")
        assert main(["a.md", "-q"]) == EXIT_OK
        runs = list((in_tmp / "tool-out").iterdir())
        assert len(runs) == 1
        assert (runs[0] / "a.html").is_file()

    def test_default_output_does_not_depend_on_cwd(self, in_tmp, monkeypatch):
        """起動位置を変えても出力先は動かない。"""
        write(in_tmp / "work" / "a.md", "# A\n")
        monkeypatch.chdir(in_tmp / "work")
        assert main(["a.md", "-q"]) == EXIT_OK
        assert not (in_tmp / "work" / "out").exists()
        assert list((in_tmp / "tool-out").iterdir())

    def test_each_run_gets_its_own_folder(self, in_tmp, monkeypatch):
        """複数回実行しても混ざらず、前回の出力も消えない。"""
        write(in_tmp / "a.md", "# A\n")
        write(in_tmp / "b.md", "# B\n")
        stamps = iter(["20260914-100000", "20260914-100001"])
        monkeypatch.setattr(cli, "timestamp_slug", lambda *a, **kw: next(stamps))

        assert main(["a.md", "-q"]) == EXIT_OK
        assert main(["b.md", "-q"]) == EXIT_OK

        base = in_tmp / "tool-out"
        assert (base / "20260914-100000" / "a.html").is_file()
        assert (base / "20260914-100001" / "b.html").is_file()

    def test_explicit_output_has_no_timestamp_folder(self, in_tmp):
        """-o で指定した場合はそのまま使う（バッチ運用の出力先を動かさない）。"""
        write(in_tmp / "a.md", "# A\n")
        assert main(["a.md", "-o", "dist", "-q"]) == EXIT_OK
        assert (in_tmp / "dist" / "a.html").is_file()

    def test_explicit_output_file(self, in_tmp):
        write(in_tmp / "a.md", "# A\n")
        assert main(["a.md", "-o", "report.html", "-q"]) == EXIT_OK
        assert (in_tmp / "report.html").is_file()

    def test_directory_is_recursive_and_keeps_structure(self, in_tmp):
        write(in_tmp / "docs" / "a.md", "# A\n")
        write(in_tmp / "docs" / "sub" / "b.md", "# B\n")
        assert main(["docs", "-o", "out", "-q"]) == EXIT_OK
        assert (in_tmp / "out" / "a.html").is_file()
        assert (in_tmp / "out" / "sub" / "b.html").is_file()

    def test_non_markdown_is_skipped(self, in_tmp):
        write(in_tmp / "docs" / "a.md", "# A\n")
        write(in_tmp / "docs" / "note.txt", "text\n")
        assert main(["docs", "-o", "out", "-q"]) == EXIT_OK
        assert not (in_tmp / "out" / "note.html").exists()

    def test_duplicate_inputs_convert_once(self, in_tmp, capsys):
        write(in_tmp / "a.md", "# A\n")
        assert main(["a.md", "a.md", "-o", "out", "-v"]) == EXIT_OK
        assert capsys.readouterr().err.count("→") == 1

    def test_type_override_changes_template(self, in_tmp):
        write(in_tmp / "a.md", "---\ntype: minutes\n---\n\n# A\n")
        assert main(["a.md", "-o", "a.html", "--type", "incident", "-q"]) == EXIT_OK
        assert 'content="incident"' in (in_tmp / "a.html").read_text(encoding="utf-8")

    def test_unknown_type_warns_but_succeeds(self, in_tmp, capsys):
        write(in_tmp / "a.md", "---\ntype: minuets\n---\n\n# A\n")
        assert main(["a.md", "-o", "out", "-q"]) == EXIT_OK
        assert "未知の type" in capsys.readouterr().err

    def test_dry_run_writes_nothing(self, in_tmp):
        write(in_tmp / "a.md", "# A\n")
        assert main(["a.md", "--dry-run", "-q"]) == EXIT_OK
        assert not (in_tmp / "tool-out").exists()

    def test_empty_directory_fails(self, in_tmp, capsys):
        (in_tmp / "docs").mkdir()
        assert main(["docs", "-q"]) == EXIT_FAILED
        assert "見つかりませんでした" in capsys.readouterr().err


class TestOutputOption:
    """-o に .html を渡したときの扱い。"""

    def test_single_file_writes_that_file(self, in_tmp):
        write(in_tmp / "a.md", "# A\n")
        assert main(["a.md", "-o", "report.html", "-q"]) == EXIT_OK
        assert (in_tmp / "report.html").is_file()

    def test_multiple_inputs_warn(self, in_tmp, capsys):
        """複数を 1 つの HTML にはまとめられないことを伝える。"""
        write(in_tmp / "docs" / "a.md", "# A\n")
        write(in_tmp / "docs" / "b.md", "# B\n")
        main(["docs", "-o", "out.html", "-q"])
        assert "ディレクトリ名として扱います" in capsys.readouterr().err

    def test_multiple_inputs_still_convert(self, in_tmp):
        write(in_tmp / "docs" / "a.md", "# A\n")
        write(in_tmp / "docs" / "b.md", "# B\n")
        assert main(["docs", "-o", "out.html", "-q"]) == EXIT_OK
        assert (in_tmp / "out.html" / "a.html").is_file()

    def test_strict_makes_it_an_error(self, in_tmp):
        write(in_tmp / "docs" / "a.md", "# A\n")
        write(in_tmp / "docs" / "b.md", "# B\n")
        assert main(["docs", "-o", "out.html", "-q", "--strict"]) == EXIT_FAILED

    def test_directory_output_does_not_warn(self, in_tmp, capsys):
        write(in_tmp / "docs" / "a.md", "# A\n")
        main(["docs", "-o", "out", "-q"])
        assert "ディレクトリ名として扱います" not in capsys.readouterr().err

    def test_single_file_does_not_warn(self, in_tmp, capsys):
        write(in_tmp / "a.md", "# A\n")
        main(["a.md", "-o", "report.html", "-q"])
        assert "ディレクトリ名として扱います" not in capsys.readouterr().err


class TestCollisions:
    """別ディレクトリの同名ファイルが黙って上書きされないこと。"""

    def test_both_files_are_kept(self, in_tmp):
        write(in_tmp / "a" / "doc.md", "# A\n")
        write(in_tmp / "b" / "doc.md", "# B\n")
        assert main(["a/doc.md", "b/doc.md", "-o", "out", "-q"]) == EXIT_OK

        produced = sorted(p.name for p in (in_tmp / "out").iterdir())
        assert produced == ["doc-b.html", "doc.html"]

    def test_contents_are_not_mixed_up(self, in_tmp):
        write(in_tmp / "a" / "doc.md", "# A の見出し\n")
        write(in_tmp / "b" / "doc.md", "# B の見出し\n")
        main(["a/doc.md", "b/doc.md", "-o", "out", "-q"])
        assert "A の見出し" in (in_tmp / "out" / "doc.html").read_text(encoding="utf-8")
        assert "B の見出し" in (in_tmp / "out" / "doc-b.html").read_text(encoding="utf-8")

    def test_collision_is_reported(self, in_tmp, capsys):
        write(in_tmp / "a" / "doc.md", "# A\n")
        write(in_tmp / "b" / "doc.md", "# B\n")
        main(["a/doc.md", "b/doc.md", "-o", "out", "-q"])
        assert "出力先が重なる" in capsys.readouterr().err

    def test_three_way_collision(self, in_tmp):
        for name in ("a", "b", "c"):
            write(in_tmp / name / "doc.md", f"# {name}\n")
        main(["a/doc.md", "b/doc.md", "c/doc.md", "-o", "out", "-q"])
        produced = sorted(p.name for p in (in_tmp / "out").iterdir())
        assert produced == ["doc-b.html", "doc-c.html", "doc.html"]

    def test_same_parent_name_falls_back_to_number(self, in_tmp):
        """親ディレクトリ名まで同じ場合は連番でずらす。"""
        write(in_tmp / "x" / "docs" / "doc.md", "# X\n")
        write(in_tmp / "y" / "docs" / "doc.md", "# Y\n")
        main(["x/docs/doc.md", "y/docs/doc.md", "-o", "out", "-q"])
        produced = sorted(p.name for p in (in_tmp / "out").iterdir())
        assert produced == ["doc-docs.html", "doc.html"]

    def test_no_collision_within_one_directory_tree(self, in_tmp):
        """階層を保つので、ディレクトリ指定では元から衝突しない。"""
        write(in_tmp / "docs" / "doc.md", "# A\n")
        write(in_tmp / "docs" / "sub" / "doc.md", "# B\n")
        assert main(["docs", "-o", "out", "-q"]) == EXIT_OK
        assert (in_tmp / "out" / "doc.html").is_file()
        assert (in_tmp / "out" / "sub" / "doc.html").is_file()

    def test_index_lists_both(self, in_tmp):
        write(in_tmp / "a" / "doc.md", "---\ntitle: A\n---\n\n本文\n")
        write(in_tmp / "b" / "doc.md", "---\ntitle: B\n---\n\n本文\n")
        main(["a/doc.md", "b/doc.md", "-o", "out", "--index", "-q"])
        html = (in_tmp / "out" / "index.html").read_text(encoding="utf-8")
        assert 'href="doc.html"' in html and 'href="doc-b.html"' in html


class TestRunDirectory:
    """実行ごとの出力フォルダは、同じ秒に重なっても分かれること。"""

    def test_same_second_gets_a_separate_folder(self, in_tmp, monkeypatch):
        write(in_tmp / "a.md", "# A\n")
        write(in_tmp / "b.md", "# B\n")
        monkeypatch.setattr(cli, "timestamp_slug", lambda *a, **kw: "20260916-120000")

        assert main(["a.md", "-q"]) == EXIT_OK
        assert main(["b.md", "-q"]) == EXIT_OK

        base = in_tmp / "tool-out"
        assert (base / "20260916-120000" / "a.html").is_file()
        assert (base / "20260916-120000-2" / "b.html").is_file()

    def test_existing_folder_is_never_reused(self, in_tmp, monkeypatch):
        """他のプロセスが先に作っていたフォルダには書き込まない。"""
        write(in_tmp / "a.md", "# A\n")
        monkeypatch.setattr(cli, "timestamp_slug", lambda *a, **kw: "20260916-120000")
        taken = in_tmp / "tool-out" / "20260916-120000"
        taken.mkdir(parents=True)
        (taken / "先客.html").write_text("x", encoding="utf-8")

        assert main(["a.md", "-q"]) == EXIT_OK
        assert sorted(p.name for p in taken.iterdir()) == ["先客.html"]
        assert (in_tmp / "tool-out" / "20260916-120000-2" / "a.html").is_file()

    def test_reservation_is_exclusive(self, in_tmp):
        """作成そのものが排他操作であること（存在確認と作成の隙間を作らない）。"""
        base = in_tmp / "runs"
        first = cli._reserve_run_dir(base, "20260916-120000")
        second = cli._reserve_run_dir(base, "20260916-120000")
        assert first != second
        assert first.is_dir() and second.is_dir()

    def test_dry_run_creates_nothing(self, in_tmp):
        write(in_tmp / "a.md", "# A\n")
        assert main(["a.md", "-q", "--dry-run"]) == EXIT_OK
        assert not (in_tmp / "tool-out").exists()

    def test_empty_run_folder_is_removed(self, in_tmp, monkeypatch):
        """1 件も書き出せなかったときに、空のフォルダを残さない。"""
        write(in_tmp / "a.md", "# A\n")
        monkeypatch.setattr(cli, "_convert_one", lambda *a, **kw: None)
        assert main(["a.md", "-q"]) == EXIT_FAILED
        assert list((in_tmp / "tool-out").iterdir()) == []

    def test_explicit_output_is_not_timestamped(self, in_tmp):
        write(in_tmp / "a.md", "# A\n")
        assert main(["a.md", "-o", "dist", "-q"]) == EXIT_OK
        assert (in_tmp / "dist" / "a.html").is_file()


class TestStrict:
    """--strict: 警告を失敗扱いにする（バッチでの取りこぼし防止）。"""

    def test_unknown_type_fails(self, in_tmp):
        write(in_tmp / "a.md", "---\ntype: minuets\n---\n\n# A\n")
        assert main(["a.md", "-o", "out", "-q", "--strict"]) == EXIT_FAILED

    def test_no_warning_succeeds(self, in_tmp):
        write(in_tmp / "a.md", "---\ntype: minutes\n---\n\n# A\n")
        assert main(["a.md", "-o", "out", "-q", "--strict"]) == EXIT_OK

    def test_output_is_still_written(self, in_tmp):
        """失敗扱いでも変換結果は書き出す（内容の確認はできるように）。"""
        write(in_tmp / "a.md", "---\ntype: minuets\n---\n\n# A\n")
        main(["a.md", "-o", "out", "-q", "--strict"])
        assert (in_tmp / "out" / "a.html").is_file()

    def test_missing_image_fails(self, in_tmp):
        write(in_tmp / "a.md", "![図](nope.png)\n")
        assert main(["a.md", "-o", "out", "-q", "--strict"]) == EXIT_FAILED

    def test_missing_input_fails(self, in_tmp):
        write(in_tmp / "a.md", "# A\n")
        assert main(["a.md", "nope.md", "-o", "out", "-q", "--strict"]) == EXIT_FAILED

    def test_collision_fails(self, in_tmp):
        write(in_tmp / "a" / "doc.md", "# A\n")
        write(in_tmp / "b" / "doc.md", "# B\n")
        assert main(["a/doc.md", "b/doc.md", "-o", "out", "-q", "--strict"]) == EXIT_FAILED

    def test_reason_is_reported(self, in_tmp, capsys):
        write(in_tmp / "a.md", "---\ntype: minuets\n---\n\n# A\n")
        main(["a.md", "-o", "out", "-q", "--strict"])
        assert "--strict" in capsys.readouterr().err

    def test_warning_count_in_summary(self, in_tmp, capsys):
        write(in_tmp / "a.md", "---\ntype: minuets\n---\n\n# A\n")
        main(["a.md", "-o", "out"])
        assert "警告 1 件" in capsys.readouterr().err


class TestIndex:
    def test_index_lists_every_document(self, in_tmp):
        write(in_tmp / "docs" / "a.md", "---\ntype: minutes\ntitle: 定例\n---\n\n## 議題\n")
        write(in_tmp / "docs" / "sub" / "b.md", "---\ntitle: メモ\n---\n\n本文\n")
        assert main(["docs", "-o", "out", "--index", "-q"]) == EXIT_OK

        html = (in_tmp / "out" / "index.html").read_text(encoding="utf-8")
        assert "定例" in html and "メモ" in html
        assert 'href="a.html"' in html
        assert 'href="sub/b.html"' in html

    def test_no_index_without_flag(self, in_tmp):
        write(in_tmp / "docs" / "a.md", "# A\n")
        assert main(["docs", "-o", "out", "-q"]) == EXIT_OK
        assert not (in_tmp / "out" / "index.html").exists()

    def test_index_is_self_contained(self, in_tmp):
        write(in_tmp / "docs" / "a.md", "# A\n")
        main(["docs", "-o", "out", "--index", "-q"])
        html = (in_tmp / "out" / "index.html").read_text(encoding="utf-8")
        assert "<style>" in html and "http://" not in html


class TestUserConfig:
    def test_cwd_config_is_picked_up(self, in_tmp):
        write(in_tmp / "config.yaml", "profiles:\n  incident:\n    watermark: false\n")
        write(in_tmp / "a.md", "---\ntype: incident\n---\n\n# A\n")
        assert main(["a.md", "-o", "a.html", "-q"]) == EXIT_OK
        assert '<div class="dm-watermark"' not in (in_tmp / "a.html").read_text(encoding="utf-8")

    def test_broken_config_is_a_config_error(self, in_tmp, capsys):
        write(in_tmp / "bad.yaml", "profiles:\n  default:\n    theme: nope\n")
        write(in_tmp / "a.md", "# A\n")
        assert main(["a.md", "-c", "bad.yaml"]) == EXIT_CONFIG_ERROR
        assert "設定エラー" in capsys.readouterr().err
