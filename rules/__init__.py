"""ルール層 (意味づけ) のレジストリ。

ルールは「Markdown → HTML 変換後の DOM を BeautifulSoup で触る関数」。
Markdown 拡張を書くより読み書きしやすく、種類の追加が
**関数 1 つ + YAML 数行** で済むようにしている。

    @rule("todo_checklist")
    def todo_checklist(soup, meta):
        '''「## ToDo」直下のリストをチェックボックス付きにする。'''
        ...

シグネチャは ``(soup: BeautifulSoup, meta: dict) -> None``。戻り値は見ない。
テンプレートに値を渡したいときは ``derived(meta)`` の dict に入れる
（テンプレート側から ``derived.summary`` のように参照できる）。
書き方の誤りを指摘したいときは ``warn(meta, ...)``。
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Set

RuleFunc = Callable[[Any, Dict[str, Any]], None]

#: 名前 → ルール関数。``@rule`` で登録される。
RULES: Dict[str, RuleFunc] = {}

#: ルールがテンプレートへ値を渡すための、meta 内の予約キー。
DERIVED_KEY = "_derived"


class RuleError(RuntimeError):
    """ルールの登録・実行に関する問題。"""


def rule(name: str) -> Callable[[RuleFunc], RuleFunc]:
    """ルール関数を ``name`` で登録するデコレータ。"""
    def decorator(func: RuleFunc) -> RuleFunc:
        if name in RULES:
            raise RuleError(f"ルール名が重複しています: {name}")
        RULES[name] = func
        return func
    return decorator


def derived(meta: Dict[str, Any]) -> Dict[str, Any]:
    """ルールがテンプレートへ渡す値の置き場を返す (無ければ作る)。"""
    store = meta.get(DERIVED_KEY)
    if not isinstance(store, dict):
        store = {}
        meta[DERIVED_KEY] = store
    return store


#: ルールが出した警告の置き場 (``derived(meta)`` の中のキー)。
WARNINGS_KEY = "warnings"


def warn(meta: Dict[str, Any], message: str) -> None:
    """ルールから警告を出す。converter が変換結果の警告に混ぜる。"""
    derived(meta).setdefault(WARNINGS_KEY, []).append(message)


def take_warnings(meta: Dict[str, Any]) -> List[str]:
    """ルールが出した警告を取り出す (二重に数えないよう、取り出したら消す)。"""
    return derived(meta).pop(WARNINGS_KEY, [])


def unknown_rules(names: Iterable[str]) -> Set[str]:
    """未登録のルール名を返す。設定の検証用。"""
    return {name for name in names if name not in RULES}


def apply_rules(names: Iterable[str], soup: Any, meta: Dict[str, Any]) -> None:
    """``names`` のルールを順に適用する。未登録なら ``RuleError``。

    ルール内で落ちた場合も、どのルールが原因かを添えて ``RuleError`` にする
    （1 ファイルの失敗で一括変換全体が止まらないようにするため）。
    """
    for name in names:
        try:
            func = RULES[name]
        except KeyError:
            raise RuleError(f"未登録のルール: {name}") from None
        try:
            func(soup, meta)
        except RuleError:
            raise
        except Exception as e:
            raise RuleError(f"ルール '{name}' の適用に失敗しました: {e}") from e


def rule_descriptions() -> List[tuple]:
    """``(名前, 説明)`` の一覧を名前順で返す。``--list-rules`` 用。"""
    out = []
    for name in sorted(RULES):
        doc = (RULES[name].__doc__ or "").strip().splitlines()
        out.append((name, doc[0].strip() if doc else ""))
    return out


# ルール関数の登録。import した時点で RULES が埋まる。
from rules import (  # noqa: E402,F401
    common, incident, minutes, period, procedure, spec, tables, weekly, weekly3,
)
