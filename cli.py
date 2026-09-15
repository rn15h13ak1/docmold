"""docmold CLI 本体。

main() は薄いオーケストレーターで、責務ごとに以下へ分割している:
  _list_types / _list_rules — 一覧表示だけで終了するサブコマンド相当
  _collect_sources          — 入力パス (ファイル / ディレクトリ) の展開
  _convert_one              — 1 ファイルの変換と書き出し
  _write_index              — 一括変換時の索引 HTML

種類の判定ロジックは持たない。front matter の ``type`` と ``--type`` だけを見る。
"""
from __future__ import annotations

import argparse
import datetime
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from config import ConfigError, Config, load_config
from converter import ConversionError, convert_file
from frontmatter import FrontMatterError
from renderer import RenderError, build_css, get_environment
from rules import RuleError, rule_descriptions

# docmold.py / cli.py が置かれているディレクトリ。フルパス起動でも
# 既定 config.yaml とテンプレートを解決できるようにする。
SCRIPT_DIR = Path(__file__).resolve().parent

# Exit code
EXIT_OK = 0
EXIT_FAILED = 1          # 1 件以上の変換に失敗
EXIT_CONFIG_ERROR = 2
EXIT_INTERRUPTED = 130

#: 一括変換で拾う拡張子。
MARKDOWN_EXTS = (".md", ".markdown")

#: 索引 HTML のファイル名。
INDEX_FILENAME = "index.html"

#: 既定の出力先。docmold.py と同じディレクトリの out/ に固定する。
#: メニューやバッチをどこから起動しても出力先が動かないようにするため、
#: CWD 基準にはしない（-o で明示した場合だけ CWD 基準になる）。
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "out"


@dataclass
class _Entry:
    """索引 HTML の 1 行。"""

    href: str
    title: str
    type: str
    source: str


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="docmold",
        description="Markdown を、内容の種類ごとに表現を変えた自己完結 HTML に変換します。",
        epilog=(
            "種類は .md の front matter に 'type: minutes' のように書きます。"
            " 指定できる種類は --list-types で確認できます。"
        ),
    )
    parser.add_argument(
        "inputs",
        nargs="*",
        help=".md ファイル、またはそれを含むディレクトリ (複数可)",
    )
    parser.add_argument(
        "-o", "--output",
        help="出力先。入力が 1 ファイルならファイルパス、それ以外はディレクトリ (default: ./out)",
    )
    parser.add_argument(
        "-t", "--type",
        dest="type_override",
        help="front matter の type を上書きする (既存の .md を書き換えずに別表現で出したいとき)",
    )
    parser.add_argument("-c", "--config", help="設定ファイルのパス (default: CWD/config.yaml → 同梱)")
    parser.add_argument("--index", action="store_true", help="出力ディレクトリに索引 HTML を生成する")
    parser.add_argument("--list-types", action="store_true", help="指定できる種類の一覧を表示して終了")
    parser.add_argument("--list-rules", action="store_true", help="登録済みルールの一覧を表示して終了")
    parser.add_argument("--dry-run", action="store_true", help="変換の検証のみ。HTML は書き出さない")
    parser.add_argument("-v", "--verbose", action="store_true", help="1 件ごとの変換結果を出力")
    parser.add_argument("-q", "--quiet", action="store_true", help="警告以外の進捗を抑制")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        config = load_config(args.config, default_search_dir=SCRIPT_DIR)
    except (ConfigError, RuleError) as e:
        sys.stderr.write(f"設定エラー: {e}\n")
        return EXIT_CONFIG_ERROR

    if args.list_types:
        _list_types(config)
        return EXIT_OK
    if args.list_rules:
        _list_rules()
        return EXIT_OK

    if not args.inputs:
        sys.stderr.write(
            "変換対象を指定してください (例: docmold.py 議事録.md)\n"
            "  種類の一覧: docmold.py --list-types\n"
        )
        return EXIT_CONFIG_ERROR

    if args.type_override and args.type_override not in config.profiles:
        sys.stderr.write(
            f"設定エラー: --type '{args.type_override}' は未定義です"
            f" (指定できる type: {', '.join(config.type_names)})\n"
        )
        return EXIT_CONFIG_ERROR

    try:
        sources, missing = _collect_sources(args.inputs)
    except OSError as e:
        sys.stderr.write(f"入力エラー: {e}\n")
        return EXIT_CONFIG_ERROR

    for path in missing:
        sys.stderr.write(f"警告: 見つかりません: {path}\n")
    if not sources:
        sys.stderr.write("変換対象の .md が見つかりませんでした。\n")
        return EXIT_FAILED

    single_file = len(sources) == 1 and Path(args.inputs[0]).is_file()
    output_dir, output_file = _resolve_output(args.output, single_file)

    if not args.quiet:
        sys.stderr.write(f"設定ファイル: {config.config_path}\n")
        sys.stderr.write(f"対象: {len(sources)} ファイル\n")
        sys.stderr.write(f"出力先: {output_file or output_dir}\n")

    entries: List[_Entry] = []
    failed = 0
    try:
        for source, root in sources:
            destination = output_file or _destination_for(source, root, output_dir)
            entry = _convert_one(source, destination, config, args)
            if entry is None:
                failed += 1
            else:
                entries.append(entry)
    except KeyboardInterrupt:
        sys.stderr.write("\n中断しました。\n")
        return EXIT_INTERRUPTED

    if args.index and entries and not args.dry_run:
        index_path = (output_file.parent if output_file else output_dir) / INDEX_FILENAME
        try:
            _write_index(index_path, entries, config)
        except (OSError, RenderError) as e:
            sys.stderr.write(f"索引の生成に失敗しました: {e}\n")
            failed += 1
        else:
            if not args.quiet:
                sys.stderr.write(f"索引: {index_path}\n")

    if not args.quiet:
        sys.stderr.write(f"完了: 成功 {len(entries)} 件 / 失敗 {failed} 件\n")
        if entries and not args.dry_run:
            sys.stderr.write(f"出力先: {output_file or output_dir}\n")
    return EXIT_FAILED if failed else EXIT_OK


# =============================================================================
# 一覧表示
# =============================================================================

def _list_types(config: Config) -> None:
    """front matter に書ける種類を、テンプレート / テーマと合わせて表示する。"""
    print("front matter に 'type: <名前>' で指定します。\n")
    width = max((len(name) for name in config.type_names), default=4)
    print(f"  {'名前'.ljust(width)}  {'テンプレート':<16} {'テーマ':<12} 説明")
    print(f"  {'-' * width}  {'-' * 16} {'-' * 12} {'-' * 20}")
    for name in config.type_names:
        profile = config.profile(name)
        print(
            f"  {name.ljust(width)}  {profile.template:<16} "
            f"{profile.theme:<12} {profile.description}"
        )
    print(f"\n設定ファイル: {config.config_path}")


def _list_rules() -> None:
    """登録済みのルール (意味づけ) を表示する。"""
    print("profiles.<type>.rules に並べると、その順で DOM 後処理が走ります。\n")
    items = rule_descriptions()
    width = max((len(name) for name, _ in items), default=4)
    for name, description in items:
        print(f"  {name.ljust(width)}  {description}")


# =============================================================================
# 入出力の解決
# =============================================================================

def _collect_sources(inputs: Sequence[str]) -> Tuple[List[Tuple[Path, Path]], List[str]]:
    """入力パスを ``(ファイル, 基準ディレクトリ)`` の一覧に展開する。

    基準ディレクトリは出力側でディレクトリ構造を保つために使う。
    同じファイルを 2 回指定しても 1 度しか変換しない。
    """
    sources: List[Tuple[Path, Path]] = []
    missing: List[str] = []
    seen = set()

    for raw in inputs:
        path = Path(raw).expanduser()
        if path.is_dir():
            found = sorted(
                child for child in path.rglob("*")
                if child.is_file() and child.suffix.lower() in MARKDOWN_EXTS
            )
            for child in found:
                key = child.resolve()
                if key not in seen:
                    seen.add(key)
                    sources.append((child, path))
        elif path.is_file():
            key = path.resolve()
            if key not in seen:
                seen.add(key)
                sources.append((path, path.parent))
        else:
            missing.append(raw)

    return sources, missing


def _resolve_output(output: Optional[str], single_file: bool,
                    timestamp: Optional[str] = None) -> Tuple[Path, Optional[Path]]:
    """``(出力ディレクトリ, 単一出力ファイル or None)`` を返す。

    ``-o`` が無いときは **ツール同梱の out/<YYYYMMDD-HHMMSS>/**。
    起動位置に依存させず、実行ごとにフォルダを分けることで、
    複数回実行した結果が混ざったり、前回の出力が上書きされたりしないようにする。

    ``-o`` を指定した場合はそのパスをそのまま使う（CWD 基準・タイムスタンプ無し）。
    バッチやタスクスケジューラから決まった場所に出す用途を壊さないため。
    """
    if output is None:
        return DEFAULT_OUTPUT_DIR / (timestamp or timestamp_slug()), None

    path = Path(output).expanduser()
    # 単一ファイル入力で、拡張子付きの出力が指定されたときだけファイル扱いにする。
    if single_file and path.suffix.lower() in (".html", ".htm"):
        return path.parent, path
    return path, None


def timestamp_slug(now: Optional[datetime.datetime] = None) -> str:
    """出力フォルダ名向けのタイムスタンプ (YYYYMMDD-HHMMSS)。"""
    return (now or datetime.datetime.now()).strftime("%Y%m%d-%H%M%S")


def _destination_for(source: Path, root: Path, output_dir: Path) -> Path:
    """入力の階層を出力ディレクトリに写した ``.html`` のパスを返す。"""
    try:
        relative = source.resolve().relative_to(root.resolve())
    except ValueError:
        relative = Path(source.name)
    return output_dir / relative.with_suffix(".html")


# =============================================================================
# 変換
# =============================================================================

def _convert_one(source: Path, destination: Path, config: Config,
                 args: argparse.Namespace) -> Optional[_Entry]:
    """1 ファイルを変換して書き出す。失敗したら None。"""
    try:
        result = convert_file(source, config, type_override=args.type_override)
    except (ConversionError, FrontMatterError, RenderError, RuleError, ConfigError) as e:
        sys.stderr.write(f"エラー: {source}: {e}\n")
        return None

    for warning in result.warnings:
        sys.stderr.write(f"警告: {source}: {warning}\n")

    if not args.dry_run:
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(result.html, encoding="utf-8")
        except OSError as e:
            sys.stderr.write(f"エラー: {destination}: 書き出せません: {e}\n")
            return None

    if args.verbose and not args.quiet:
        action = "検証" if args.dry_run else "出力"
        sys.stderr.write(f"  [{result.profile_name}] {source} → {destination} ({action})\n")

    return _Entry(
        href=_relative_href(destination),
        title=result.title,
        type=result.profile_name,
        source=str(source),
    )


def _relative_href(destination: Path) -> str:
    """索引からのリンク。索引は出力ディレクトリ直下に置くため相対パスで持つ。"""
    return destination.name if destination.parent == Path(".") else str(destination)


def _write_index(index_path: Path, entries: List[_Entry], config: Config) -> None:
    """一括変換の索引 HTML を書き出す (本体と同じく自己完結 1 ファイル)。"""
    base = index_path.parent
    rows = []
    for entry in entries:
        try:
            href = Path(entry.href).resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            href = Path(entry.href).as_posix()
        rows.append({"href": href, "title": entry.title, "type": entry.type, "source": entry.source})

    template = get_environment().get_template(INDEX_FILENAME)
    html = template.render(
        title="docmold 索引",
        entries=sorted(rows, key=lambda row: (row["type"], row["title"])),
        generated_at=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        css=build_css(config, config.profile("default")),
    )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(html, encoding="utf-8")
