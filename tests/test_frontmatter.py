"""frontmatter: front matter の分離。"""
from __future__ import annotations

import pytest

from frontmatter import FrontMatterError, meta_to_text, split_front_matter


class TestSplit:
    def test_no_front_matter(self):
        meta, body = split_front_matter("# 見出し\n本文\n")
        assert meta == {}
        assert body == "# 見出し\n本文\n"

    def test_basic(self):
        meta, body = split_front_matter("---\ntype: minutes\ntitle: 定例\n---\n\n## 決定\n")
        assert meta == {"type": "minutes", "title": "定例"}
        assert body == "\n## 決定\n"

    def test_crlf(self):
        meta, body = split_front_matter("---\r\ntype: spec\r\n---\r\n本文\r\n")
        assert meta["type"] == "spec"
        assert body == "本文\r\n"

    def test_bom_is_skipped(self):
        meta, _ = split_front_matter("﻿---\ntype: weekly\n---\n本文\n")
        assert meta["type"] == "weekly"

    def test_document_end_marker(self):
        meta, body = split_front_matter("---\ntype: spec\n...\n本文\n")
        assert meta["type"] == "spec"
        assert body == "本文\n"

    def test_empty_front_matter(self):
        meta, body = split_front_matter("---\n\n---\n本文\n")
        assert meta == {}
        assert body == "本文\n"

    def test_hr_is_not_front_matter(self):
        """本文中の水平線は front matter として食わない。"""
        meta, body = split_front_matter("本文\n\n---\n\n続き\n")
        assert meta == {}
        assert body.startswith("本文")

    def test_broken_yaml(self):
        with pytest.raises(FrontMatterError, match="YAML"):
            split_front_matter("---\ntype: [壊れて\n---\n本文\n")

    def test_scalar_front_matter_rejected(self):
        with pytest.raises(FrontMatterError, match="マッピング"):
            split_front_matter("---\nただの文字列\n---\n本文\n")


class TestMetaToText:
    def test_list_is_joined(self):
        assert meta_to_text(["山田", "佐藤"]) == "山田, 佐藤"

    def test_none_is_empty(self):
        assert meta_to_text(None) == ""

    def test_bool(self):
        assert meta_to_text(True) == "はい"

    def test_dict(self):
        assert meta_to_text({"担当": "山田"}) == "担当: 山田"
