"""
docmold 対話メニュー
====================
変換対象・種類・出力先を対話形式で選んで実行する。

  python3 menu.py                  # メニューを表示
  python3 menu.py --config my.yaml # 設定ファイルを指定

種類（type）は本来 .md の front matter に書くもので、このメニューでは
「front matter に従う」が既定。別の表現で出したいときだけ上書きを選ぶ。

無人実行はこのメニューではなく本体を直接呼ぶこと:
  python3 docmold.py docs -o out --index
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import cli as docmold_cli
    import config as docmold_config
except ModuleNotFoundError as e:
    # menu.bat のダブルクリック起動で、依存が入っていない場合に
    # トレースバックではなく対処を表示する
    if e.name not in ("yaml", "markdown", "jinja2", "bs4"):
        raise
    print(f"必要なライブラリ {e.name} が入っていません。")
    print("次のコマンドでインストールしてください:")
    print("    pip install -r requirements.txt")
    sys.exit(2)

WIDTH = 60
TOOL_DIR = Path(__file__).resolve().parent
SCRIPT = TOOL_DIR / "docmold.py"
HISTORY_PATH = Path.home() / ".docmold_menu.json"

#: 変換対象として数える拡張子（本体と揃える）。
MARKDOWN_EXTS = (".md", ".markdown")

ACTION_CONVERT = "convert"
ACTION_TYPES = "types"
ACTION_RULES = "rules"

ACTIONS = [
    (ACTION_CONVERT, "変換する", "Markdown を自己完結 HTML に変換する"),
    (ACTION_TYPES, "種類の一覧", "front matter の type に書ける名前を表示する"),
    (ACTION_RULES, "ルールの一覧", "種類ごとの意味づけ（後処理）を表示する"),
]

# 終了コード
EXIT_OK = 0
EXIT_EOF = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130


# ===========================================================================
# 表示・入力
# ===========================================================================


def hr(char="="):
    print(char * WIDTH)


def print_menu(title: str, items: list, back_label: str = "戻る",
               default: int = None, default_mark: str = "既定") -> int:
    """
    メニューを表示して選択番号を返す。0 = 戻る / 終了。
    default_mark は既定値の由来を示すラベル（前回の選択なら「前回」）。
    """
    while True:
        print()
        hr()
        print(f"  {title}")
        hr()
        for i, item in enumerate(items, 1):
            mark = f" ←{default_mark}" if default == i else ""
            print(f"  {i}. {item}{mark}")
        hr("-")
        print(f"  0. {back_label}")
        hr()
        prompt = ("番号を入力してください"
                  + (f" [Enter={default}]: " if default else ": "))
        choice = input(prompt).strip()
        if not choice and default:
            return default
        if choice == "0":
            return 0
        if choice.isdigit() and 1 <= int(choice) <= len(items):
            return int(choice)
        print("  ※ 無効な入力です。もう一度入力してください。")


def input_text(prompt: str, default: str = "", validate=None,
               hint: str = "") -> str:
    """
    文字列を入力させる。空 Enter は default を採用する。
    default が無い状態で空 Enter を押した場合は None（キャンセル）を返す。
    """
    suffix = f" [Enter={default}]" if default else "（空 Enter で戻る）"
    while True:
        answer = input(f"  {prompt}{suffix}: ").strip()
        if not answer:
            if default:
                return default
            return None
        # ドラッグ＆ドロップで付く引用符を落とす（Windows のパスでよく付く）。
        answer = answer.strip('"').strip("'")
        if validate is None or validate(answer):
            return answer
        print(f"  ※ {hint}")


def confirm(prompt: str, default_yes: bool = True) -> bool:
    """y/n を尋ねる。空 Enter は default_yes。"""
    suffix = " [Y/n]: " if default_yes else " [y/N]: "
    while True:
        answer = input(f"  {prompt}{suffix}").strip().lower()
        if not answer:
            return default_yes
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("  ※ y か n で答えてください。")


# ===========================================================================
# 入力パスの検証
# ===========================================================================


def resolve_input(value: str) -> Path:
    """入力文字列をパスにする（相対パスはメニューの実行位置基準）。"""
    return Path(value).expanduser()


def is_convertible(value: str) -> bool:
    """変換対象として成立するパスか（.md か、.md を含むディレクトリ）。"""
    path = resolve_input(value.strip('"').strip("'"))
    if path.is_file():
        return path.suffix.lower() in MARKDOWN_EXTS
    if path.is_dir():
        return any(count_markdown(path))
    return False


def count_markdown(directory: Path):
    """ディレクトリ配下の .md を列挙する（存在確認にも使う）。"""
    return sorted(
        child for child in directory.rglob("*")
        if child.is_file() and child.suffix.lower() in MARKDOWN_EXTS
    )


def describe_input(value: str) -> str:
    """入力パスを 1 行で説明する。"""
    path = resolve_input(value)
    if path.is_file():
        return f"{path}（1 ファイル）"
    if path.is_dir():
        return f"{path}（{len(count_markdown(path))} ファイル）"
    return f"{path}（見つかりません）"


# ===========================================================================
# 前回値の記憶
# ===========================================================================


def load_history() -> dict:
    """前回の入力値を読む。壊れていても既定値で続行する。"""
    try:
        with open(HISTORY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_history(data: dict) -> None:
    """入力値を保存する。書けなくても実行は妨げない。"""
    try:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ===========================================================================
# 種類の選択
# ===========================================================================


def load_profiles(config_path: str):
    """設定を読む。読めない場合は (None, 理由) を返す。"""
    try:
        return docmold_config.load_config(config_path or None,
                                          default_search_dir=TOOL_DIR), ""
    except docmold_config.ConfigError as e:
        return None, str(e)


def choose_type(config) -> str:
    """種類の上書きを選ぶ。「front matter に従う」なら空文字、戻るなら None。"""
    names = config.type_names
    items = ["front matter に従う（既定）"] + [
        f"{name} ― {config.profile(name).description or '説明なし'}" for name in names
    ]
    choice = print_menu("種類（type）", items, default=1)
    if choice == 0:
        return None
    if choice == 1:
        return ""
    return names[choice - 2]


def choose_output(history: dict) -> str:
    """出力先を選ぶ。既定なら空文字（-o を渡さない）、戻るなら None。

    既定はツール同梱の out/<タイムスタンプ>/。実行のたびにフォルダが分かれるため、
    複数回実行しても結果が混ざらず、前回の出力も消えない。
    """
    last = history.get("output", "")
    items = [
        f"既定（{docmold_cli.DEFAULT_OUTPUT_DIR}/<日時>/）",
        "場所を指定する",
    ]
    choice = print_menu("出力先", items, default=2 if last else 1)
    if choice == 0:
        return None
    if choice == 1:
        return ""
    return input_text("出力先のパス", default=last)


# ===========================================================================
# 実行内容の組み立て
# ===========================================================================


def build_args(input_path: str, *, config_path: str = "", output: str = "",
               type_override: str = "", index: bool = False,
               dry_run: bool = False) -> list:
    """本体に渡すコマンドライン引数を組み立てる。"""
    args = [input_path]
    if config_path:
        args += ["--config", config_path]
    if output:
        args += ["-o", output]
    if type_override:
        args += ["--type", type_override]
    if index:
        args.append("--index")
    if dry_run:
        args.append("--dry-run")
    args.append("--verbose")
    return args


def run_docmold(args: list) -> int:
    """本体を実行して終了コードを返す。"""
    if not SCRIPT.is_file():
        print(f"\n  ※ 本体が見つかりません: {SCRIPT}")
        return 127
    print()
    hr("-")
    try:
        completed = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=Path.cwd())
    except KeyboardInterrupt:
        print("\n  中断しました。")
        return EXIT_INTERRUPTED
    return completed.returncode


def latest_output(output: str):
    """開くべき出力先を返す。無ければ None。

    既定（-o なし）のときは本体がタイムスタンプ付きのフォルダを作るため、
    out/ 配下の最新のフォルダを開く。
    """
    if output:
        destination = resolve_input(output)
        if destination.is_dir():
            return destination
        return destination.parent if destination.parent.is_dir() else None

    base = docmold_cli.DEFAULT_OUTPUT_DIR
    if not base.is_dir():
        return None
    folders = [child for child in base.iterdir() if child.is_dir()]
    return max(folders, key=lambda child: child.name) if folders else None


def open_in_explorer(path: Path) -> bool:
    """出力先をエクスプローラ / Finder で開く。開けなければ False。"""
    try:
        if sys.platform == "win32":
            os.startfile(str(path))  # noqa: S606 - Windows の既定動作で開く
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=True)
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
        return True
    except (OSError, subprocess.SubprocessError, AttributeError):
        return False


# ===========================================================================
# 各操作の対話
# ===========================================================================


def collect_inputs(config, history: dict) -> dict:
    """変換に必要な入力を集める。戻る場合は None。"""
    input_path = input_text(
        "変換する .md またはディレクトリ",
        default=history.get("input", ""),
        validate=is_convertible,
        hint=".md ファイルか、.md を含むディレクトリを指定してください。",
    )
    if not input_path:
        return None
    print(f"    → {describe_input(input_path)}")

    type_override = choose_type(config)
    if type_override is None:
        return None

    output = choose_output(history)
    if output is None:
        return None

    # 索引は複数ファイルをまとめたときだけ意味があるので、ディレクトリ入力時に尋ねる。
    index = False
    if resolve_input(input_path).is_dir():
        index = confirm("索引 HTML（index.html）も作りますか？",
                        default_yes=bool(history.get("index", True)))

    return {"input": input_path, "type": type_override, "output": output, "index": index}


def run_convert(config, config_path: str, history: dict):
    """変換を対話で実行する。戻る場合は None。"""
    print()
    hr()
    print("  変換する")
    hr()

    inputs = collect_inputs(config, history)
    if inputs is None:
        return None

    choice = print_menu(
        "実行モード",
        ["変換して書き出す", "検証のみ（--dry-run・HTML を書き出しません）"],
        default=1,
    )
    if choice == 0:
        return None
    dry_run = (choice == 2)

    # 記憶するのは入力値のみ。実行前に保存し、途中で失敗しても次回に活きるようにする。
    history.update({
        "action": ACTION_CONVERT,
        "input": inputs["input"],
        "output": inputs["output"],
        "type": inputs["type"],
        "index": inputs["index"],
    })
    save_history(history)

    rc = run_docmold(build_args(
        inputs["input"],
        config_path=config_path,
        output=inputs["output"],
        type_override=inputs["type"],
        index=inputs["index"],
        dry_run=dry_run,
    ))

    if rc == EXIT_OK and not dry_run:
        target = latest_output(inputs["output"])
        if target is not None and confirm("出力先を開きますか？", default_yes=False):
            if not open_in_explorer(target):
                print(f"  ※ 開けませんでした。手動で確認してください: {target}")
    return rc


def show_listing(option: str, config_path: str) -> int:
    """--list-types / --list-rules を本体に委譲して表示する。"""
    args = [option]
    if config_path:
        args += ["--config", config_path]
    return run_docmold(args)


# ===========================================================================
# エントリポイント
# ===========================================================================


def describe_config(config_path: str) -> str:
    """設定の状態を 1 行で表す。読めない場合は理由を返す。"""
    config, error = load_profiles(config_path)
    if config is None:
        return f"※ {error}"
    return f"{config.config_path}（{len(config.profiles)} 種類）"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="docmold 対話メニュー",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="無人実行には docmold.py を直接使ってください。",
    )
    parser.add_argument(
        "--config",
        default="",
        help="設定ファイルのパス（省略時: CWD/config.yaml → 同梱の profiles.yaml）",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    history = load_history()
    last_action = history.get("action")
    default_choice = next(
        (i for i, (key, _, _) in enumerate(ACTIONS, 1) if key == last_action), 1
    )

    items = [f"{label} ― {desc}" for _, label, desc in ACTIONS]

    try:
        while True:
            print()
            hr()
            print("  docmold（Markdown → 自己完結 HTML）")
            hr()
            print(f"  設定: {describe_config(args.config)}")

            choice = print_menu("操作を選択", items, back_label="終了",
                                default=default_choice, default_mark="前回")
            if choice == 0:
                print("  終了します。")
                sys.exit(EXIT_OK)

            action = ACTIONS[choice - 1][0]
            if action == ACTION_CONVERT:
                config, error = load_profiles(args.config)
                if config is None:
                    print(f"\n  ※ 設定を読めません: {error}")
                    input("\n  Enter キーでメニューに戻ります...")
                    continue
                rc = run_convert(config, args.config, history)
            elif action == ACTION_TYPES:
                rc = show_listing("--list-types", args.config)
            else:
                rc = show_listing("--list-rules", args.config)

            if rc is not None:
                print()
                hr("-")
                print(f"  終了コード: {rc}")
                default_choice = choice
                history["action"] = action
                save_history(history)
                input("\n  Enter キーでメニューに戻ります...")
    except EOFError:
        print("\n  入力が終了しました。")
        sys.exit(EXIT_EOF)
    except KeyboardInterrupt:
        print("\n  中断しました。")
        sys.exit(EXIT_INTERRUPTED)


if __name__ == "__main__":
    main()
