"""
サンプル HTML を再生成する
==========================
examples/*.md を変換し、examples/html/ に出力する。生成物もリポジトリで管理し、
変換処理を変えたときの見た目の差分をレビューできるようにするためのもの。

    python3 tools/build_examples.py            # 再生成する
    python3 tools/build_examples.py --check    # 最新かどうか確認するだけ

--check は生成物が古い場合に終了コード 1 を返す（tests/test_examples.py と同じ判定）。

索引 HTML も --reproducible 相当（生成時刻を埋め込まない）で作るため、管理対象に含める。
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cli  # noqa: E402
from config import load_config  # noqa: E402
from converter import convert_file  # noqa: E402

SOURCE_DIR = ROOT / "examples"
OUTPUT_DIR = SOURCE_DIR / "html"

#: 生成物の先頭に入れる注記。手で編集しても次回の再生成で消えることを明示する。
BANNER = (
    "<!-- このファイルは tools/build_examples.py が生成します。"
    "手で編集しないでください。 -->\n"
)


#: 索引 HTML のファイル名（生成物に含める）。
INDEX_NAME = cli.INDEX_FILENAME


def source_files() -> list:
    """変換対象の .md を名前順で返す。"""
    return sorted(SOURCE_DIR.glob("*.md"))


def render(path: Path) -> str:
    """1 ファイル分の HTML を生成する（ファイルには書き出さない）。"""
    return BANNER + convert_file(path, _config()).html


def render_index(output_dir: Path) -> str:
    """索引 HTML を生成する（生成時刻は埋め込まない）。"""
    config = _config()
    entries = []
    for source in source_files():
        result = convert_file(source, config)
        entries.append(cli._Entry(
            href=str(destination(source, output_dir)),
            title=result.title,
            type=result.profile_name,
            source=f"examples/{source.name}",
            date=cli._entry_date(result.meta),
        ))

    index_path = output_dir / INDEX_NAME
    cli._write_index(index_path, entries, config, reproducible=True)
    html = BANNER + index_path.read_text(encoding="utf-8")
    index_path.write_text(html, encoding="utf-8")
    return html


def _config():
    return load_config(default_search_dir=ROOT)


def destination(path: Path, output_dir: Path = OUTPUT_DIR) -> Path:
    return output_dir / f"{path.stem}.html"


def stale_files(output_dir: Path = OUTPUT_DIR) -> list:
    """生成物が実際の出力と食い違っているものを返す。書き換えはしない。"""
    stale = []
    index = output_dir / INDEX_NAME
    if not index.is_file():
        stale.append((index, "未生成"))
    else:
        # 索引は書き出してからでないと内容を作れないため、一時ディレクトリで作る。
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            if index.read_text(encoding="utf-8") != render_index(Path(temporary)):
                stale.append((index, "内容が古い"))

    for source in source_files():
        target = destination(source, output_dir)
        if not target.is_file():
            stale.append((target, "未生成"))
        elif target.read_text(encoding="utf-8") != render(source):
            stale.append((target, "内容が古い"))

    # .md を消したのに HTML が残っている場合も検出する。
    expected = {destination(source, output_dir) for source in source_files()}
    expected.add(output_dir / INDEX_NAME)
    if output_dir.is_dir():
        for found in sorted(output_dir.glob("*.html")):
            if found not in expected:
                stale.append((found, "対応する .md が無い"))
    return stale


def build(output_dir: Path = OUTPUT_DIR, quiet: bool = False) -> int:
    """再生成して、書き換えた件数を返す。

    内容が変わらないファイルには触れない（無駄な差分を作らないため）。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    changed = 0

    def report(message: str) -> None:
        if not quiet:
            print(message)

    for source in source_files():
        target = destination(source, output_dir)
        html = render(source)
        if target.is_file() and target.read_text(encoding="utf-8") == html:
            continue
        target.write_text(html, encoding="utf-8")
        report(f"  更新: {_display(target)}")
        changed += 1

    index = output_dir / INDEX_NAME
    previous = index.read_text(encoding="utf-8") if index.is_file() else ""
    if render_index(output_dir) != previous:
        report(f"  更新: {_display(index)}")
        changed += 1

    expected = {destination(source, output_dir) for source in source_files()}
    expected.add(index)
    for found in sorted(output_dir.glob("*.html")):
        if found not in expected:
            found.unlink()
            report(f"  削除: {_display(found)}（対応する .md が無い）")
            changed += 1

    return changed


def _display(path: Path) -> str:
    """ROOT 配下なら相対パスで、外なら絶対パスで表示する。"""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="サンプル HTML を再生成する")
    parser.add_argument("--check", action="store_true",
                        help="再生成せず、最新かどうかだけ確認する")
    args = parser.parse_args()

    if args.check:
        stale = stale_files()
        if not stale:
            print(f"サンプル HTML は最新です（本文 {len(source_files())} 件 + 索引）")
            return 0
        print("サンプル HTML が古くなっています:")
        for path, reason in stale:
            print(f"  {_display(path)} — {reason}")
        print("\n  python3 tools/build_examples.py で再生成してください。")
        return 1

    changed = build()
    if changed:
        print(f"{changed} 件を更新しました。差分を確認してコミットしてください。")
    else:
        print(f"変更はありません（本文 {len(source_files())} 件 + 索引とも最新）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
