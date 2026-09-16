"""front matter の日付に関するルール。

「開始日だけ書いて、期間は変換時に組み立てる」ための後処理。ここでは DOM ではなく
front matter を書き換える（テンプレートは書き換わった値を表として出す）。
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, Optional, Tuple

from rules import keywords, rule, warn
from rules.common import normalize

#: 1 期間の日数。開始日を 1 日目と数える（月曜開始なら終了は日曜）。
PERIOD_DAYS = 7

#: 期間の区切り。
PERIOD_SEPARATOR = " 〜 "

#: 受け付ける日付の書き方。区切り文字は出力でもそのまま使う。
_DATE_RE = re.compile(r"\A(\d{4})([-/.])(\d{1,2})\2(\d{1,2})\Z")


@rule("period_range")
def period_range(soup: Any, meta: Dict[str, Any]) -> None:
    """front matter の「開始日」から「期間」を組み立てる。

    ``開始日: 2026-03-09`` と書くと ``期間: 2026-03-09 〜 2026-03-15`` になる
    （``PERIOD_DAYS`` 日間）。``期間`` を直接書いてある場合はそのまま使う。
    """
    start_key = _find_key(meta, "period_start")
    if start_key is None:
        return

    period_key = keywords.get("period")[0]
    if _text(meta.get(_find_key(meta, "period"))):
        warn(meta, f"{period_key} と {start_key} の両方があるため、"
                   f"{period_key} をそのまま使いました")
        return

    parsed = _parse_date(_text(meta.get(start_key)))
    if parsed is None:
        warn(meta, f"{start_key}「{_text(meta.get(start_key))}」を日付として読めませんでした"
                   f"（例: 2026-03-09）")
        return

    start, separator = parsed
    end = start + timedelta(days=PERIOD_DAYS - 1)
    meta[period_key] = _format(start, separator) + PERIOD_SEPARATOR + _format(end, separator)


def _find_key(meta: Dict[str, Any], group: str) -> Optional[str]:
    """front matter から、検出語に一致するキー名を返す。"""
    targets = [normalize(word) for word in keywords.get(group)]
    for key in meta:
        if isinstance(key, str) and not key.startswith("_") and normalize(key) in targets:
            return key
    return None


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _parse_date(text: str) -> Optional[Tuple[date, str]]:
    """``2026-03-09`` を ``(date, 区切り文字)`` にする。読めなければ None。"""
    match = _DATE_RE.match(text)
    if not match:
        return None
    year, separator, month, day = match.groups()
    try:
        return date(int(year), int(month), int(day)), separator
    except ValueError:
        return None


def _format(value: date, separator: str) -> str:
    return f"{value.year:04d}{separator}{value.month:02d}{separator}{value.day:02d}"
