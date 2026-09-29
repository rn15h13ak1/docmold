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
        assert data["期間"] == "2026-03-09(月) 〜 2026-03-15(日)"
        assert warnings == []

    def test_period_crosses_the_month(self):
        data, _ = run({"開始日": "2026-03-30"})
        assert data["期間"] == "2026-03-30(月) 〜 2026-04-05(日)"

    def test_slash_is_kept(self):
        data, _ = run({"開始日": "2026/03/09"})
        assert data["期間"] == "2026/03/09(月) 〜 2026/03/15(日)"

    def test_single_digits_are_padded(self):
        data, _ = run({"開始日": "2026-3-9"})
        assert data["期間"] == "2026-03-09(月) 〜 2026-03-15(日)"

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
        assert run({"起算日": "2026-03-09"})[0]["期間"] == "2026-03-09(月) 〜 2026-03-15(日)"
        assert run({"start": "2026-03-09"})[0]["期間"] == "2026-03-09(月) 〜 2026-03-15(日)"


class TestInDocument:
    def test_meta_table_shows_the_period(self, config):
        from converter import convert_text

        result = convert_text(
            "---\ntype: weekly\ntitle: 週報\n開始日: 2026-03-09\n---\n\n## 進捗\n\n本文\n",
            config,
        )
        assert "2026-03-09(月) 〜 2026-03-15(日)" in result.html
        assert result.warnings == []

    def test_period_is_still_accepted(self, config):
        from converter import convert_text

        result = convert_text(
            "---\ntype: weekly\ntitle: 週報\n期間: 2026-03-09 〜 2026-03-15\n---\n\n## 進捗\n\n本文\n",
            config,
        )
        # 自分で書いた期間は書き換えない（曜日も足さない）。
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
    return f"---\ntype: weekly3\ntitle: 課題\n{meta}\n---\n\n## トピックス\n\n連絡\n\n{body}\n"


class TestColumnPeriods:
    def titles_of(self, html: str) -> list:
        import re

        return re.findall(r'class="dm-column__title">([^<]*)', html)

    def test_three_columns_get_their_own_range(self, config):
        from converter import convert_text

        result = convert_text(columns_doc("前週", "今週", "来週の予定"), config)
        assert self.titles_of(result.html)[:3] == [
            "前週（3/2(月)〜3/8(日)）", "今週（3/9(月)〜3/15(日)）", "来週の予定（3/16(月)〜3/22(日)）",
        ]

    def test_period_key_works_too(self, config):
        from converter import convert_text

        result = convert_text(
            columns_doc("前週", "今週", "来週", meta="期間: 2026-03-09 〜 2026-03-15"), config)
        assert self.titles_of(result.html)[:3] == [
            "前週（3/2(月)〜3/8(日)）", "今週（3/9(月)〜3/15(日)）", "来週（3/16(月)〜3/22(日)）",
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


class TestColumnDates:
    """取り込み先のファイル名の日付が、その列の週と合っているか。"""

    def convert(self, tmp_path, start: str, names: list, config):
        from converter import convert_file

        (tmp_path / "parts").mkdir(exist_ok=True)
        lines = []
        for heading, name in zip(("前週", "今週", "来週の予定"), names):
            (tmp_path / "parts" / name).write_text(
                "---\ntype: fragment\n---\n\n### バグ\n\n- AB-1｜処理中｜x\n",
                encoding="utf-8")
            lines.append(f"  {heading}: parts/{name}")
        parent = tmp_path / "親.md"
        parent.write_text(
            f"---\ntype: weekly3\ntitle: t\n開始日: {start}\n取り込み:\n"
            + "\n".join(lines)
            + "\n---\n\n## トピックス\n\n### x\n\n本文\n",
            encoding="utf-8")
        return convert_file(parent, config)

    NAMES = ["2026-03-09.md", "2026-03-16.md", "2026-03-23.md"]

    def test_matching_dates_are_silent(self, tmp_path, config):
        result = self.convert(tmp_path, "2026-03-16", self.NAMES, config)
        assert result.warnings == []

    def test_shifted_start_is_reported(self, tmp_path, config):
        # 開始日だけ翌週にずらし、取り込み先を直し忘れた場合。
        result = self.convert(tmp_path, "2026-03-23", self.NAMES, config)
        assert len(result.warnings) == 3
        assert "前週" in result.warnings[0]
        assert "2026-03-16 の週ではありません" in result.warnings[0]

    def test_one_slot_left_behind_is_reported(self, tmp_path, config):
        names = ["2026-03-09.md", "2026-03-09.md", "2026-03-23.md"]
        result = self.convert(tmp_path, "2026-03-16", names, config)
        assert len(result.warnings) == 1
        assert "今週" in result.warnings[0]

    def test_names_without_a_date_are_not_checked(self, tmp_path, config):
        result = self.convert(tmp_path, "2026-03-16", ["先週.md", "今回.md", "次回.md"],
                              config)
        assert result.warnings == []

    def test_compact_dates_are_read(self, tmp_path, config):
        names = ["20260309.md", "20260316.md", "20260323.md"]
        assert self.convert(tmp_path, "2026-03-16", names, config).warnings == []
        assert self.convert(tmp_path, "2026-03-23", names, config).warnings

    def test_without_a_start_nothing_is_checked(self, tmp_path, config):
        from converter import convert_file

        (tmp_path / "parts").mkdir()
        (tmp_path / "parts" / "2026-01-01.md").write_text(
            "---\ntype: fragment\n---\n\n### バグ\n\n本文\n", encoding="utf-8")
        parent = tmp_path / "親.md"
        parent.write_text(
            "---\ntype: weekly3\ntitle: t\n取り込み:\n  前週: parts/2026-01-01.md\n"
            "  今週: parts/2026-01-01.md\n  来週: parts/2026-01-01.md\n---\n\n"
            "## トピックス\n\n### x\n\n本文\n", encoding="utf-8")
        assert convert_file(parent, config).warnings == []
