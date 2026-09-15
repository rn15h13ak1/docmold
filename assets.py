"""自己完結 HTML のための資材の取り込み。

閉域ネットワークでは CDN に出られないため、外部参照ゼロを前提とする。
CSS / JS / 画像はすべて 1 ファイルに埋め込む。
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
THEMES_DIR = SCRIPT_DIR / "themes"
ASSETS_DIR = SCRIPT_DIR / "assets"

#: 同梱を想定する Mermaid のファイル名（CDN 禁止対策でリポジトリに置く）。
MERMAID_FILENAME = "mermaid.min.js"

#: 埋め込みを許す画像の拡張子。
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico"}

#: 1 枚あたりの埋め込み上限。これを超えると base64 でファイルが肥大するため見送る。
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def read_theme_css(name: str) -> str:
    """``themes/<name>.css`` を読む。無ければ空文字。"""
    path = THEMES_DIR / f"{name}.css"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def read_mermaid_js() -> Tuple[str, Optional[str]]:
    """同梱の mermaid.min.js を読む。``(js, 警告)`` を返す。"""
    path = ASSETS_DIR / MERMAID_FILENAME
    if not path.is_file():
        return "", (
            f"mermaid が有効ですが {path} がありません — 図は描画されません"
            f" (CDN は使えないため {MERMAID_FILENAME} を assets/ に置いてください)"
        )
    return path.read_text(encoding="utf-8"), None


def embed_images(soup: Any, base_dir: Optional[Path]) -> List[str]:
    """ローカル画像を data URI にして埋め込む。返り値は警告の一覧。"""
    warnings: List[str] = []
    if base_dir is None:
        return warnings

    for image in soup.find_all("img"):
        src = (image.get("src") or "").strip()
        if not src or _is_external(src):
            continue

        path = (base_dir / src).resolve()
        if not path.is_file():
            warnings.append(f"画像が見つかりません: {src}")
            continue
        if path.suffix.lower() not in IMAGE_EXTS:
            warnings.append(f"埋め込み対象外の画像形式です: {src}")
            continue

        size = path.stat().st_size
        if size > MAX_IMAGE_BYTES:
            warnings.append(
                f"画像が大きいため埋め込みません ({size / 1024 / 1024:.1f} MB): {src}"
            )
            continue

        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        image["src"] = f"data:{mime};base64,{data}"

    return warnings


def _is_external(src: str) -> bool:
    """``http://`` / ``https://`` / ``data:`` など、埋め込み不要・不可の参照か。"""
    lowered = src.lower()
    return (
        lowered.startswith(("http://", "https://", "data:", "//"))
        or lowered.startswith("file://")
    )
