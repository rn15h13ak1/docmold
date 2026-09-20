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
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from config import ConfigError, Config, load_config
from converter import ConversionError, convert_file
from frontmatter import FrontMatterError, meta_to_text
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


class _Reporter:
    """警告を出しつつ件数を数える。

    --strict で「警告があれば失敗扱い」にするため、出しっぱなしにせず集計する。
    """

    def __init__(self) -> None:
        self.count = 0

    def warn(self, message: str) -> None:
        self.count += 1
        sys.stderr.write(f"警告: {message}\n")


@dataclass
class _Entry:
    """索引 HTML の 1 行。

    ``source`` は入力の起点からの相対パス。変換した端末の絶対パスを索引に
    載せると、配布物やコミットにディレクトリ構成とユーザ名が残るため。
    """

    href: str
    title: str
    type: str
    source: str
    date: str = ""


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
    parser.add_argument(
        "--reproducible", action="store_true",
        help="出力に生成時刻を埋め込まない（索引を差分管理したいとき）",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="警告があれば失敗扱いにする（終了コード 1）。バッチや定期実行での取りこぼし防止",
    )
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

    reporter = _Reporter()
    for path in missing:
        reporter.warn(f"見つかりません: {path}")
    if not sources:
        sys.stderr.write("変換対象の .md が見つかりませんでした。\n")
        return EXIT_FAILED

    single_file = len(sources) == 1 and Path(args.inputs[0]).is_file()
    output_dir, output_file = _resolve_output(
        args.output, single_file, reporter, reserve=not args.dry_run)

    if not args.quiet:
        sys.stderr.write(f"設定ファイル: {config.config_path}\n")
        sys.stderr.write(f"対象: {len(sources)} ファイル\n")
        sys.stderr.write(f"出力先: {output_file or output_dir}\n")

    plan = _plan_destinations(sources, output_dir, output_file, reporter)

    entries: List[_Entry] = []
    failed = 0
    try:
        for source, destination, source_root in plan:
            entry = _convert_one(source, destination, source_root, config, args, reporter)
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
            _write_index(index_path, entries, config, reproducible=args.reproducible)
        except (OSError, RenderError) as e:
            sys.stderr.write(f"索引の生成に失敗しました: {e}\n")
            failed += 1
        else:
            if not args.quiet:
                sys.stderr.write(f"索引: {index_path}\n")

    if not args.quiet:
        summary = f"完了: 成功 {len(entries)} 件 / 失敗 {failed} 件"
        if reporter.count:
            summary += f" / 警告 {reporter.count} 件"
        sys.stderr.write(summary + "\n")
        if entries and not args.dry_run:
            sys.stderr.write(f"出力先: {output_file or output_dir}\n")

    if output_file is None and args.output is None and not args.dry_run:
        _remove_if_empty(output_dir)

    if args.strict and reporter.count:
        sys.stderr.write(
            f"--strict: 警告が {reporter.count} 件あるため失敗として扱います。\n"
        )
        return EXIT_FAILED
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
                    reporter: Optional["_Reporter"] = None,
                    reserve: bool = False,
                    timestamp: Optional[str] = None) -> Tuple[Path, Optional[Path]]:
    """``(出力ディレクトリ, 単一出力ファイル or None)`` を返す。

    ``-o`` が無いときは **ツール同梱の out/<YYYYMMDD-HHMMSS>/**。
    起動位置に依存させず、実行ごとにフォルダを分けることで、
    複数回実行した結果が混ざったり、前回の出力が上書きされたりしないようにする。

    ``-o`` を指定した場合はそのパスをそのまま使う（CWD 基準・タイムスタンプ無し）。
    バッチやタスクスケジューラから決まった場所に出す用途を壊さないため。
    """
    if output is None:
        stamp = timestamp or timestamp_slug()
        if not reserve:
            return DEFAULT_OUTPUT_DIR / stamp, None
        return _reserve_run_dir(DEFAULT_OUTPUT_DIR, stamp), None

    path = Path(output).expanduser()
    # 単一ファイル入力で、拡張子付きの出力が指定されたときだけファイル扱いにする。
    looks_like_file = path.suffix.lower() in (".html", ".htm")
    if single_file and looks_like_file:
        return path.parent, path

    if looks_like_file and reporter is not None:
        # 複数ファイルを 1 つの HTML にはまとめられない。黙ってディレクトリを作ると
        # 「out.html という名前のフォルダ」ができて分かりにくいため、理由を伝える。
        reporter.warn(
            f"-o '{output}' はディレクトリ名として扱います"
            f"（入力が複数のため、1 つの HTML にはまとめられません）"
        )
    return path, None


def timestamp_slug(now: Optional[datetime.datetime] = None) -> str:
    """出力フォルダ名向けのタイムスタンプ (YYYYMMDD-HHMMSS)。"""
    return (now or datetime.datetime.now()).strftime("%Y%m%d-%H%M%S")


#: 同一秒に重なったときに試す連番の上限。
_MAX_RUN_SUFFIX = 100


def _reserve_run_dir(base: Path, timestamp: str) -> Path:
    """実行ごとの出力フォルダを排他的に作って返す。

    同じ秒に複数のプロセスが走ると、フォルダ名が衝突して出力が混ざる。
    「存在するか調べてから作る」では、調べた直後に別プロセスが作る隙間が残るため、
    ``exist_ok=False`` で **作成そのものを排他操作にする**。
    既に使われていれば連番をずらして、別のフォルダを確保する。
    """
    candidates = [timestamp] + [f"{timestamp}-{n}" for n in range(2, _MAX_RUN_SUFFIX)]
    for name in candidates:
        candidate = base / name
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            continue
        except OSError as e:
            raise ConversionError(f"{candidate}: 出力フォルダを作成できません: {e}") from e

    raise ConversionError(
        f"{base}: 同じ時刻の出力フォルダが {_MAX_RUN_SUFFIX} 個あります。古い出力を整理してください"
    )


def _plan_destinations(sources: List[Tuple[Path, Path]], output_dir: Path,
                       output_file: Optional[Path],
                       reporter: "_Reporter") -> List[Tuple[Path, Path, Path]]:
    """``(入力, 出力先, 入力の起点)`` の一覧を、出力先が重ならないように決める。

    別々のディレクトリに同名の .md があると出力先がぶつかり、黙って上書きされて
    片方の結果が消える。名前をずらして両方残し、その旨を警告する。

    起点は索引の「ファイル」列を相対パスで出すために持ち回る。
    """
    if output_file is not None:
        return [(source, output_file, root) for source, root in sources]

    plan: List[Tuple[Path, Path, Path]] = []
    taken = set()
    for source, root in sources:
        destination = _destination_for(source, root, output_dir)
        if destination in taken:
            original = destination
            destination = _unique_destination(destination, source, taken)
            reporter.warn(
                f"出力先が重なるため名前を変えました: {source} → {destination.name}"
                f"（{original.name} は先に変換したファイルが使用）"
            )
        taken.add(destination)
        plan.append((source, destination, root))
    return plan


def _unique_destination(destination: Path, source: Path, taken: set) -> Path:
    """重複しない出力先を作る。親ディレクトリ名を足し、それでも重なれば連番。"""
    stem = destination.stem
    parent_name = source.parent.name
    if parent_name:
        candidate = destination.with_name(f"{stem}-{parent_name}.html")
        if candidate not in taken:
            return candidate
        stem = f"{stem}-{parent_name}"

    for number in range(2, 1000):
        candidate = destination.with_name(f"{stem}-{number}.html")
        if candidate not in taken:
            return candidate
    raise ConversionError(f"{source}: 出力先の名前を決められません")


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

def _convert_one(source: Path, destination: Path, source_root: Path, config: Config,
                 args: argparse.Namespace, reporter: "_Reporter") -> Optional[_Entry]:
    """1 ファイルを変換して書き出す。失敗したら None。"""
    try:
        result = convert_file(source, config, type_override=args.type_override)
    except (ConversionError, FrontMatterError, RenderError, RuleError, ConfigError) as e:
        sys.stderr.write(f"エラー: {source}: {e}\n")
        return None

    for warning in result.warnings:
        reporter.warn(f"{source}: {warning}")

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
        source=_relative_source(source, source_root),
        date=_entry_date(result.meta),
    )


def _entry_date(meta: dict) -> str:
    """索引に出す日付を front matter から拾う。見つからなければ空。

    文書の種類ごとに日付のキーが違う（日時 / 実施日 / 発生日時 / 期間 …）ため、
    keywords の index_date グループを順に見る。
    """
    from rules import keywords

    for key in keywords.get("index_date"):
        if key in meta:
            return meta_to_text(meta[key])
    return ""


def _relative_href(destination: Path) -> str:
    """索引からのリンク。索引は出力ディレクトリ直下に置くため相対パスで持つ。"""
    return destination.name if destination.parent == Path(".") else str(destination)


def _relative_source(source: Path, root: Path) -> str:
    """索引に出す入力パス。入力の起点からの相対で返す。

    絶対パスを渡して変換しても索引は相対で出る。配布物やコミットに、変換した
    端末のディレクトリ構成とユーザ名を残さないため。起点の外にあるなど相対化
    できないときは、せめてホームディレクトリを ``~`` に畳んで個人名を隠す。
    """
    try:
        return source.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        pass
    try:
        return ("~" / source.resolve().relative_to(Path.home())).as_posix()
    except (ValueError, RuntimeError):
        return source.as_posix()


#: 日付らしき並びを取り出す (2026-09-14 / 2026/9/14 / 20260914)。
_DATE_RE = re.compile(r"(\d{4})\D?(\d{1,2})\D?(\d{1,2})")


def _write_index(index_path: Path, entries: List[_Entry], config: Config,
                 reproducible: bool = False) -> None:
    """一括変換の索引 HTML を書き出す (本体と同じく自己完結 1 ファイル)。"""
    base = index_path.parent
    rows = []
    for entry in entries:
        try:
            href = Path(entry.href).resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            href = Path(entry.href).as_posix()
        source = Path(entry.source)
        rows.append({
            "href": href,
            "title": entry.title,
            "type": entry.type,
            "source": source.as_posix(),
            # 入力のディレクトリごとに索引を区切るため、親と名前を分けて渡す。
            "group": source.parent.as_posix() if source.parent != Path(".") else "",
            "name": source.name,
            "date": entry.date,
        })

    ordered = sorted(rows, key=_index_order)
    template = get_environment().get_template(INDEX_FILENAME)
    html = template.render(
        title="docmold 索引",
        entries=ordered,
        grouped=_index_grouped(ordered),
        generated_at=(
            "" if reproducible
            else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ),
        css=build_css(config, config.profile("default")),
    )
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(html, encoding="utf-8")


def _remove_if_empty(directory: Path) -> None:
    """確保しただけで使わなかった出力フォルダを片付ける。"""
    try:
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    except OSError:
        pass


def _index_grouped(rows: List[dict]) -> bool:
    """索引をディレクトリごとに区切るかどうか。

    区切るのは、入力が複数のディレクトリにまたがり、かつどの文書にも日付が
    無いときだけ。日付を持つ文書セット（議事録や週次報告）では新しい順に
    並ぶことが索引の値打ちで、ディレクトリで区切るとその順序が崩れるため。
    """
    if len({row["group"] for row in rows}) < 2:
        return False
    return not any(_date_sort_key(row["date"]) for row in rows)


def _index_order(row: dict) -> tuple:
    """索引の並び順。新しい日付から先に、日付が無いものは最後にまとめる。

    日付を持たない文書セットは、入力のディレクトリ順 → ファイル名順に並べる。
    設計書のように日付を書かない文書は、タイトルの辞書順に混ぜてしまうと
    第1編〜第4編のような構成が索引から読み取れなくなるため。

    日付を持つ文書の並びは変えない。同じ日付の中の順序（種類 → タイトル）も
    従来のままにし、パスは最後の同点決着にだけ使う。
    """
    key = _date_sort_key(row["date"])
    path = (row["group"], row["name"])
    if key:
        return (0, _reverse(key), row["type"], row["title"], path)
    return (1, 0, path, row["type"], row["title"])


def _date_sort_key(text: str) -> str:
    """日付らしき並びを YYYYMMDD に正規化する。拾えなければ空。"""
    match = _DATE_RE.search(text or "")
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{year}{int(month):02d}{int(day):02d}"


def _reverse(key: str) -> tuple:
    """文字列の降順ソート用キー（数値に落として符号を反転する）。"""
    return -int(key) if key else 0
