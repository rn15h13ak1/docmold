"""callout_blockquote ルールのテスト。"""
from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from rules import apply_rules


def convert(markdown_html: str) -> BeautifulSoup:
    """Markdown 変換後の DOM を模したものにルールを適用する。"""
    soup = BeautifulSoup(markdown_html, "html.parser")
    apply_rules(["callout_blockquote"], soup, {})
    return soup


class TestMarker:
    def test_title_and_body_in_one_paragraph_are_split(self):
        """``> [!warning] 見出し`` の次行に本文を続けると 1 段落になる。切り分ける。"""
        soup = convert("<blockquote><p>[!warning] よくある誤解\n本文。</p></blockquote>")
        box = soup.find("div", class_="dm-callout")
        assert "dm-callout--warn" in box["class"]
        assert box.find("p", class_="dm-callout__title").get_text() == "よくある誤解"
        assert "本文。" in box.get_text()
        assert "[!warning]" not in soup.get_text()

    def test_title_on_its_own_paragraph(self):
        """目印と本文の間に空行がある書き方でも同じ結果になる。"""
        soup = convert("<blockquote><p>[!warning] 見出し</p><p>本文。</p></blockquote>")
        box = soup.find("div", class_="dm-callout")
        assert box.find("p", class_="dm-callout__title").get_text() == "見出し"
        assert box.find_all("p")[1].get_text() == "本文。"

    def test_without_title(self):
        soup = convert("<blockquote><p>[!info]\n本文。</p></blockquote>")
        box = soup.find("div", class_="dm-callout")
        assert box.find(class_="dm-callout__title") is None
        assert box.get_text().strip() == "本文。"

    def test_unknown_kind_falls_back_to_default(self):
        """語彙は増え続けるため、知らない種別も既定の系統で通す（警告もしない）。"""
        soup = convert("<blockquote><p>[!なにか] 見出し</p></blockquote>")
        assert "dm-callout--info" in soup.find("div", class_="dm-callout")["class"]

    def test_plain_quote_is_left_alone(self):
        soup = convert("<blockquote><p>普通の引用。</p></blockquote>")
        assert soup.find(class_="dm-callout") is None
        assert soup.find("blockquote") is not None


class TestSplitting:
    def test_consecutive_callouts_are_split(self):
        """Markdown は空行だけで隔てた引用を 1 つにまとめる。段落ごとに切り直す。"""
        soup = convert(
            "<blockquote><p>[!info] A\n本文A</p><p>[!tip] B\n本文B</p></blockquote>")
        boxes = soup.find_all("div", class_="dm-callout")
        assert len(boxes) == 2
        assert "dm-callout--info" in boxes[0]["class"]
        assert "dm-callout--ok" in boxes[1]["class"]
        assert "本文A" in boxes[0].get_text() and "本文B" in boxes[1].get_text()

    def test_content_before_the_marker_stays_a_quote(self):
        soup = convert("<blockquote><p>前置き。</p><p>[!danger] 見出し</p></blockquote>")
        assert soup.find("blockquote").get_text().strip() == "前置き。"
        assert "dm-callout--danger" in soup.find("div", class_="dm-callout")["class"]

    def test_body_elements_are_kept(self):
        """表や箇条書きも、そのままコールアウトの中に入る。"""
        soup = convert(
            "<blockquote><p>[!info] 見出し</p><table><tr><td>a</td></tr></table></blockquote>")
        assert soup.find("div", class_="dm-callout").find("table") is not None

    def test_nested_callout(self):
        soup = convert(
            "<blockquote><p>[!info] 外</p>"
            "<blockquote><p>[!warning] 内</p></blockquote></blockquote>")
        outer = soup.find("div", class_="dm-callout--info")
        assert outer is not None
        assert outer.find("div", class_="dm-callout--warn") is not None


class TestFolding:
    def test_minus_is_a_closed_details(self):
        soup = convert("<blockquote><p>[!note]- 折りたたみ</p><p>中身。</p></blockquote>")
        box = soup.find("details")
        assert box is not None and not box.has_attr("open")
        assert box.find("summary", class_="dm-callout__title").get_text() == "折りたたみ"

    def test_plus_is_an_open_details(self):
        soup = convert("<blockquote><p>[!note]+ 開いた</p><p>中身。</p></blockquote>")
        assert soup.find("details").has_attr("open")

    def test_folded_without_title_gets_a_label(self):
        """``<summary>`` が空だと開けなくなるため、既定の文言を入れる。"""
        soup = convert("<blockquote><p>[!note]-\n中身。</p></blockquote>")
        assert soup.find("summary").get_text() == "詳細"


class TestKinds:
    @pytest.mark.parametrize("kind, expected", [
        ("info", "info"), ("note", "info"), ("abstract", "info"), ("quote", "info"),
        ("tip", "ok"), ("success", "ok"),
        ("warning", "warn"), ("important", "warn"), ("caution", "warn"),
        ("danger", "danger"), ("error", "danger"), ("bug", "danger"),
        ("WARNING", "warn"),  # GitHub は大文字で書く
    ])
    def test_kind_maps_to_a_system(self, kind, expected):
        soup = convert(f"<blockquote><p>[!{kind}] 見出し</p></blockquote>")
        box = soup.find(class_="dm-callout")
        assert f"dm-callout--{expected}" in box["class"]


class TestEmptyTag:
    def test_marker_only_paragraph_leaves_no_empty_tag(self):
        """目印だけの段落は捨てるが、捨てた要素を継ぎ足して空タグを残さない。"""
        soup = convert("<blockquote><p>[!warning] 題</p>"
                       "<ul><li>項目1</li><li>項目2</li></ul></blockquote>")
        box = soup.select_one(".dm-callout")
        assert [tag.name for tag in box.find_all(recursive=False)] == ["p", "ul"]
        assert "<></>" not in str(soup)

    def test_list_stays_inside_the_box(self):
        soup = convert("<blockquote><p>[!note] 題</p><ul><li>項目1</li></ul></blockquote>")
        assert soup.select_one(".dm-callout li").get_text() == "項目1"


class TestInDocument:
    def test_wiki_output_has_no_empty_tag(self, config):
        from converter import convert_text

        result = convert_text(
            "---\ntype: wiki\ntitle: t\n---\n\n## 見出し\n\n"
            "> [!warning] 題\n>\n> - 項目1\n> - 項目2\n",
            config,
        )
        assert "<></>" not in result.html
        assert result.html.count('class="dm-callout__title"') == 1

    def test_weekly3_supports_callouts(self, config):
        from converter import convert_text

        result = convert_text(
            "---\ntype: weekly3\ntitle: t\n開始日: 2026-03-09\n---\n\n"
            "## トピックス\n\n### 注意\n\n"
            "> [!warning] 取りこぼしの可能性\n>\n> - コメント履歴を取得できなかった\n\n"
            "### 連絡\n\n本文\n\n"
            "## 前週\n\n### バグ\n\n本文\n\n## 今週\n\n### バグ\n\n本文\n"
            "\n## 来週\n\n### バグ\n\n本文\n",
            config,
        )
        assert result.warnings == []
        assert 'class="dm-callout dm-callout--warn"' in result.html
        # トピックスの枠の中に収まり、枠の数は変わらない。
        assert result.html.count('class="dm-topic"') == 2
