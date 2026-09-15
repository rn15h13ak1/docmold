"""テンプレート描画 (Jinja2) と、テーマ CSS の埋め込み。

出力は 1 ファイル完結の HTML。CSS・JS・画像はすべて埋め込み、外部参照を持たない。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound
    from jinja2 import TemplateError, select_autoescape
except ImportError as e:  # pragma: no cover - 依存が無い環境向けの案内
    raise ImportError("Jinja2 is required. Install with: pip install jinja2") from e

from assets import read_mermaid_js, read_theme_css
from config import Config, Profile

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPT_DIR / "templates"

_env: Optional[Environment] = None


class RenderError(RuntimeError):
    """テンプレートの描画に失敗したときに送出。"""


def get_environment() -> Environment:
    """テンプレート環境を返す (初回だけ構築)。"""
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR), encoding="utf-8"),
            autoescape=select_autoescape(default_for_string=False, default=True),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _env


#: 表紙のあるプロファイルで、1 ページ目（表紙）のページ番号を消す。
_COVER_PAGE_CSS = """@media print {
  @page :first { @bottom-center { content: ""; } }
}"""


def build_css(config: Config, profile: Profile) -> str:
    """テーマ変数 + 共通 CSS + 印刷用 CSS を 1 本にまとめる。"""
    theme = config.theme_for(profile)
    parts = [
        f":root {{\n{theme.css_variables()}\n}}",
        read_theme_css("base"),
        read_theme_css(theme.name),
        read_theme_css("print"),
    ]
    if profile.print.cover_page:
        parts.append(_COVER_PAGE_CSS)
    return "\n\n".join(part for part in parts if part.strip())


def build_pygments_css() -> str:
    """コードハイライト用 CSS。Pygments が無い環境では空文字。"""
    try:
        from pygments.formatters import HtmlFormatter
    except ImportError:  # pragma: no cover - Pygments 無しでも変換自体は通す
        return ""
    return HtmlFormatter(style="friendly").get_style_defs(".codehilite")


def render(*, config: Config, profile: Profile, content: str, title: str,
           meta: Dict[str, Any], derived: Dict[str, Any],
           toc: List[Dict[str, Any]], meta_header: List[Dict[str, str]],
           warnings: Optional[List[str]] = None) -> str:
    """プロファイルのテンプレートを描画して HTML 文字列を返す。"""
    env = get_environment()
    try:
        template = env.get_template(profile.template)
    except TemplateNotFound:
        available = sorted(p.name for p in TEMPLATES_DIR.glob("*.html"))
        raise RenderError(
            f"profiles.{profile.name}.template: テンプレートが見つかりません:"
            f" {profile.template} (同梱: {', '.join(available)})"
        ) from None

    mermaid_js = ""
    if profile.mermaid.enabled and profile.mermaid.bundled:
        mermaid_js, warning = read_mermaid_js()
        if warning and warnings is not None:
            warnings.append(warning)

    try:
        return template.render(
            content=content,
            title=title,
            meta=meta,
            derived=derived,
            toc=toc,
            toc_numbering=profile.toc.numbering,
            meta_header=meta_header,
            profile=profile,
            theme=config.theme_for(profile),
            watermark=profile.watermark,
            print_settings=profile.print,
            css=build_css(config, profile),
            pygments_css=build_pygments_css(),
            mermaid_js=mermaid_js,
            mermaid=profile.mermaid,
        )
    except TemplateError as e:
        # テンプレートの変数名間違いなどを、スタックトレースではなく 1 行で伝える。
        raise RenderError(f"{profile.template}: 描画に失敗しました: {e}") from e
