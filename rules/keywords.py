"""ルールが本文を見分けるための語。

「出席者」「ToDo」「時刻」「状態」といった検出語をここに集約し、config.yaml から
差し替えられるようにする。表記ゆれ（「参加メンバー」「進捗状況」など）への対応で
コードを直さずに済ませるため。

既定値はコードに持つ（config.yaml が無くても動くため）。config.yaml の ``keywords:``
に書いたグループだけが差し替わり、書かなかったグループは既定のまま。
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Set

#: グループ名 → 既定の検出語。
DEFAULTS: Dict[str, List[str]] = {
    # 議事録
    "attendee": ["出席者", "参加者", "参加メンバー", "attendee", "participants"],
    "todo": ["todo", "to do", "アクション", "宿題", "持ち帰り", "action item"],
    "decision": ["決定事項", "決定", "合意事項", "decision"],
    # 作業手順書
    "step": ["手順", "step"],
    "rollback": ["切戻し", "切り戻し", "ロールバック", "rollback", "復旧手順", "リカバリ"],
    # 障害報告
    "severity": ["重要度", "深刻度", "severity", "レベル", "影響度"],
    "time_column": ["時刻", "日時", "時間", "time", "タイムスタンプ"],
    "timeline": ["時系列", "経過", "タイムライン", "timeline", "対応経過"],
    # 週次報告
    "status_column": ["状態", "ステータス", "status", "進行", "対応状況"],
    "progress_column": ["進捗", "進捗率", "達成率", "progress", "完了率"],
    # 索引に出す日付として front matter から拾うキー
    "index_date": ["日時", "日付", "date", "実施日", "作成日", "発生日時", "期間", "報告日"],
    # 状態バッジの色分け
    "status_ok": ["完了", "済", "対応済", "クローズ", "done", "closed", "ok", "正常",
                  "成功", "解決済"],
    "status_warn": ["進行中", "対応中", "作業中", "保留", "確認中", "wip", "in progress",
                    "doing", "遅延", "注意", "warn", "warning", "中"],
    "status_danger": ["未着手", "未対応", "失敗", "停止", "異常", "ng", "blocked", "todo",
                      "open", "高", "重大", "critical", "緊急"],
}

#: 設定ファイルに書けるグループ名。
GROUPS = frozenset(DEFAULTS)

#: 現在有効な検出語。変換のたびに converter が設定の内容で入れ替える。
_active: Dict[str, List[str]] = {name: list(words) for name, words in DEFAULTS.items()}


def get(group: str) -> List[str]:
    """グループの検出語を返す。"""
    try:
        return _active[group]
    except KeyError:
        raise KeyError(
            f"未知のキーワードグループ: {group}（定義済み: {', '.join(sorted(GROUPS))}）"
        ) from None


def use(overrides: Dict[str, List[str]] = None) -> None:
    """既定値に ``overrides`` を重ねて有効にする。書かれていないグループは既定のまま。"""
    _active.clear()
    _active.update({name: list(words) for name, words in DEFAULTS.items()})
    for group, words in (overrides or {}).items():
        if group in _active:
            _active[group] = list(words)


def reset() -> None:
    """既定値に戻す。"""
    use()


def unknown_groups(names: Iterable[str]) -> Set[str]:
    """設定ファイルに書かれた未知のグループ名を返す。検証用。"""
    return {name for name in names if name not in GROUPS}
