"""共通フィクスチャ。"""
from __future__ import annotations

from pathlib import Path

import pytest

from config import Config, load_config


@pytest.fixture
def config() -> Config:
    """同梱の profiles.yaml だけを読んだ設定 (ユーザ config.yaml は無視)。"""
    return load_config(default_search_dir=Path("/nonexistent"))


@pytest.fixture
def make_config(tmp_path: Path):
    """`make_config(yaml_body)` で一時のユーザ設定ファイルを作る。"""
    def _make(body: str, filename: str = "config.yaml") -> Path:
        path = tmp_path / filename
        path.write_text(body, encoding="utf-8")
        return path
    return _make


@pytest.fixture
def make_md(tmp_path: Path):
    """`make_md(本文, 名前)` で一時の .md を作る。"""
    def _make(body: str, name: str = "doc.md") -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return path
    return _make
