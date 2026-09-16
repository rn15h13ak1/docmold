"""rules/period.py: front matter の開始日から期間を組み立てる。"""
from __future__ import annotations

from bs4 import BeautifulSoup

from rules import apply_rules, take_warnings


def run(meta: dict) -> tuple:
    data = dict(meta)
    apply_rules(["period_range"], BeautifulSoup("<p>x</p>", "html.parser"), data)
    return data, take_warnings(data)


class TestPeriodRange:
    def test_start_becomes_a_one_week_period(self):
        data, warnings = run({"開始日": "2026-03-09"})
        assert data["期間"] == "2026-03-09 〜 2026-03-15"
        assert warnings == []

    def test_period_crosses_the_month(self):
        data, _ = run({"開始日": "2026-03-30"})
        assert data["期間"] == "2026-03-30 〜 2026-04-05"

    def test_slash_is_kept(self):
        data, _ = run({"開始日": "2026/03/09"})
        assert data["期間"] == "2026/03/09 〜 2026/03/15"

    def test_single_digits_are_padded(self):
        data, _ = run({"開始日": "2026-3-9"})
        assert data["期間"] == "2026-03-09 〜 2026-03-15"

    def test_existing_period_is_kept(self):
        data, warnings = run({"期間": "2026-03-01 〜 2026-03-31"})
        assert data["期間"] == "2026-03-01 〜 2026-03-31"
        assert warnings == []

    def test_both_keys_keep_the_period_and_warn(self):
        data, warnings = run({"期間": "2026-03-01 〜 2026-03-31", "開始日": "2026-03-09"})
        assert data["期間"] == "2026-03-01 〜 2026-03-31"
        assert "両方" in warnings[0]

    def test_unreadable_date_is_reported(self):
        data, warnings = run({"開始日": "3月9日"})
        assert "期間" not in data
        assert "日付として読めません" in warnings[0]

    def test_impossible_date_is_reported(self):
        _, warnings = run({"開始日": "2026-02-30"})
        assert "日付として読めません" in warnings[0]

    def test_nothing_to_do_without_a_start(self):
        data, warnings = run({"報告者": "鈴木花子"})
        assert "期間" not in data
        assert warnings == []

    def test_other_spellings_work(self):
        assert run({"起算日": "2026-03-09"})[0]["期間"] == "2026-03-09 〜 2026-03-15"
        assert run({"start": "2026-03-09"})[0]["期間"] == "2026-03-09 〜 2026-03-15"


class TestInDocument:
    def test_meta_table_shows_the_period(self, config):
        from converter import convert_text

        result = convert_text(
            "---\ntype: weekly\ntitle: 週報\n開始日: 2026-03-09\n---\n\n## 進捗\n\n本文\n",
            config,
        )
        assert "2026-03-09 〜 2026-03-15" in result.html
        assert result.warnings == []

    def test_period_is_still_accepted(self, config):
        from converter import convert_text

        result = convert_text(
            "---\ntype: weekly\ntitle: 週報\n期間: 2026-03-09 〜 2026-03-15\n---\n\n## 進捗\n\n本文\n",
            config,
        )
        assert "2026-03-09 〜 2026-03-15" in result.html

    def test_index_uses_the_built_period(self, config):
        import cli
        from converter import convert_text

        result = convert_text(
            "---\ntype: weekly\ntitle: 週報\n開始日: 2026-03-09\n---\n\n## 進捗\n\n本文\n",
            config,
        )
        # 索引の日付は front matter から拾うため、組み立てた期間が使われる。
        assert cli._entry_date(result.meta).startswith("2026-03-09")


def columns_doc(*titles: str, meta: str = "開始日: 2026-03-09") -> str:
    body = "\n\n".join(f"## {title}\n\n### バグ\n\n- AB-1｜処理中｜遅い" for title in titles)
    return f"---\ntype: columns\ntitle: 課題\n{meta}\n---\n\n## トピックス\n\n連絡\n\n{body}\n"


class TestColumnPeriods:
    def titles_of(self, html: str) -> list:
        import re

        return re.findall(r'class="dm-column__title">([^<]*)', html)

    def test_three_columns_get_their_own_range(self, config):
        from converter import convert_text

        result = convert_text(columns_doc("前週", "今週", "来週の予定"), config)
        assert self.titles_of(result.html)[:3] == [
            "前週（3/2〜3/8）", "今週（3/9〜3/15）", "来週の予定（3/16〜3/22）",
        ]

    def test_period_key_works_too(self, config):
        from converter import convert_text

        result = convert_text(
            columns_doc("前週", "今週", "来週", meta="期間: 2026-03-09 〜 2026-03-15"), config)
        assert self.titles_of(result.html)[:3] == [
            "前週（3/2〜3/8）", "今週（3/9〜3/15）", "来週（3/16〜3/22）",
        ]

    def test_range_written_by_hand_is_kept(self, config):
        from converter import convert_text

        result = convert_text(columns_doc("前週", "今週（3/9 〜 3/15）", "来週"), config)
        assert self.titles_of(result.html)[1] == "今週（3/9 〜 3/15）"

    def test_topics_heading_is_untouched(self, config):
        from converter import convert_text

        result = convert_text(columns_doc("前週", "今週", "来週"), config)
        assert "トピックス（" not in result.html

    def test_document_without_a_period_is_untouched(self, config):
        from converter import convert_text

        result = convert_text(columns_doc("前週", "今週", "来週", meta="報告者: 鈴木花子"), config)
        assert self.titles_of(result.html)[:3] == ["前週", "今週", "来週"]
