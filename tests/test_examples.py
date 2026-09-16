"""examples: 管理しているサンプル HTML が最新かどうか。

変換処理を変えると出力が変わるため、コミット済みの examples/html/ が古いままに
なりやすい。このテストが落ちたら再生成してコミットする:

    python3 tools/build_examples.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_examples  # noqa: E402

REBUILD_HINT = "python3 tools/build_examples.py で再生成してコミットしてください。"


class TestGeneratedSamples:
    def test_every_example_has_html(self):
        for source in build_examples.source_files():
            target = build_examples.destination(source)
            assert target.is_file(), f"{target.name} がありません。{REBUILD_HINT}"

    def test_index_is_included(self):
        """索引もサンプルとして管理する（--reproducible で時刻を埋め込まないため）。"""
        index = build_examples.OUTPUT_DIR / build_examples.INDEX_NAME
        assert index.is_file(), f"索引がありません。{REBUILD_HINT}"
        assert "生成 " not in index.read_text(encoding="utf-8")

    def test_samples_are_up_to_date(self):
        """処理を変えたら、このテストが落ちて再生成を促す。"""
        stale = build_examples.stale_files()
        assert not stale, (
            "サンプル HTML が古くなっています: "
            + ", ".join(f"{path.name}（{reason}）" for path, reason in stale)
            + f"。{REBUILD_HINT}"
        )

    def test_index_links_to_every_sample(self):
        index = (build_examples.OUTPUT_DIR / build_examples.INDEX_NAME).read_text(encoding="utf-8")
        for source in build_examples.source_files():
            assert f'href="{source.stem}.html"' in index, source.name

    def test_samples_are_self_contained(self):
        """外部を参照しないこと。例外は Mermaid の読み込みだけ。

        本文やスクリプトのコメントに URL が出てくることはあるため、実際に読み込みが
        走る書き方（src / href / url() / @import）だけを見る。図を使う種類は
        mermaid: cdn を指定しているため、その 1 本だけは通す。
        """
        from config import DEFAULT_MERMAID_URL

        reference = re.compile(
            r"""(?:src|href)\s*=\s*["']\s*(?:https?:)?//[^"']*|"""
            r"""url\(\s*["']?\s*(?:https?:)?//[^)"']*|@import""",
            re.IGNORECASE,
        )
        for source in build_examples.source_files():
            html = build_examples.destination(source).read_text(encoding="utf-8")
            for found in reference.findall(html):
                assert DEFAULT_MERMAID_URL in found, f"{source.name}: {found}"

    def test_only_the_diagram_sample_reaches_outside(self):
        """外部参照を持つのは、図を使う種類だけであること。"""
        from config import DEFAULT_MERMAID_URL

        outside = [
            source.name for source in build_examples.source_files()
            if DEFAULT_MERMAID_URL in build_examples.destination(source).read_text(encoding="utf-8")
        ]
        assert outside == ["設計書.md"]

    def test_diagram_sample_has_a_rendered_target(self):
        """読み込むだけでなく、描画対象の要素があること。"""
        html = build_examples.destination(
            build_examples.SOURCE_DIR / "設計書.md").read_text(encoding="utf-8")
        assert html.count('<pre class="mermaid">') == 2

    def test_banner_marks_them_as_generated(self):
        for source in build_examples.source_files():
            html = build_examples.destination(source).read_text(encoding="utf-8")
            assert html.startswith(build_examples.BANNER), source.name


class TestBuild:
    """build() は書き込みを伴うため、必ず一時ディレクトリに対して実行する。

    リポジトリの examples/html/ をテストが勝手に更新してしまうと、
    「古くなったら落ちる」監視そのものが働かなくなる。
    """

    def test_first_build_creates_every_file(self, tmp_path: Path):
        """本文 + 索引の分だけ書き出す。"""
        expected = len(build_examples.source_files()) + 1  # +1 は索引
        assert build_examples.build(tmp_path, quiet=True) == expected

    def test_second_build_changes_nothing(self, tmp_path: Path):
        """内容が同じなら書き換えない（無駄な差分を作らない）。"""
        build_examples.build(tmp_path, quiet=True)
        assert build_examples.build(tmp_path, quiet=True) == 0

    def test_orphan_html_is_removed(self, tmp_path: Path):
        """.md を消したのに残った HTML は削除される。"""
        build_examples.build(tmp_path, quiet=True)
        orphan = tmp_path / "廃止.html"
        orphan.write_text("<html></html>", encoding="utf-8")
        assert build_examples.build(tmp_path, quiet=True) == 1
        assert not orphan.exists()

    def test_stale_files_does_not_write(self, tmp_path: Path):
        """確認だけの関数が書き込まないこと。"""
        build_examples.stale_files(tmp_path)
        assert not list(tmp_path.iterdir())

    def test_render_is_deterministic(self):
        """同じ入力なら毎回同じ出力になる（生成時刻などを埋め込まない）。"""
        source = build_examples.source_files()[0]
        assert build_examples.render(source) == build_examples.render(source)

    @pytest.mark.parametrize("argv,expected", [(["--check"], 0)])
    def test_check_reports_success(self, monkeypatch, argv, expected, capsys):
        monkeypatch.setattr(sys, "argv", ["build_examples.py", *argv])
        assert build_examples.main() == expected
        assert "最新です" in capsys.readouterr().out
