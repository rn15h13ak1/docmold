"""```mermaid のコードブロックを、mermaid.js が描画できる要素に変える Markdown 拡張。

mermaid.js は ``class="mermaid"`` の要素を探して中身を図に置き換える。そのままだと
codehilite が普通のコードブロック (``<div class="codehilite"><pre><code>``) にしてしまい、
mermaid.js からは見つけられない。

fenced_code より先に走る前処理として登録し、mermaid のフェンスだけ横取りする。
他の言語のフェンスは触らないので、コードハイライトは従来どおり効く。
"""
from __future__ import annotations

import html
import re
from typing import List

try:
    from markdown.extensions import Extension
    from markdown.preprocessors import Preprocessor
except ImportError as e:  # pragma: no cover - 依存が無い環境向けの案内
    raise ImportError("Markdown is required. Install with: pip install markdown") from e

#: fenced_code の前処理の優先度。これより大きい値にして先に処理する。
_FENCED_CODE_PRIORITY = 25
PRIORITY = _FENCED_CODE_PRIORITY + 1

#: ```mermaid / ~~~mermaid の開始行。属性記法 ``` { .mermaid } も受ける。
_START_RE = re.compile(
    r"^(?P<indent>[ ]{0,3})(?P<fence>`{3,}|~{3,})[ ]*"
    r"(?:mermaid\b|\{[^}]*\.mermaid[^}]*\})[ ]*$",
    re.IGNORECASE,
)


class MermaidPreprocessor(Preprocessor):
    """mermaid のフェンスを ``<pre class="mermaid">`` に置き換える。"""

    def run(self, lines: List[str]) -> List[str]:
        output: List[str] = []
        index = 0

        while index < len(lines):
            match = _START_RE.match(lines[index])
            if not match:
                output.append(lines[index])
                index += 1
                continue

            fence = match.group("fence")
            body: List[str] = []
            index += 1
            closed = False
            while index < len(lines):
                if re.match(rf"^[ ]{{0,3}}{fence[0]}{{{len(fence)},}}[ ]*$", lines[index]):
                    closed = True
                    index += 1
                    break
                body.append(lines[index])
                index += 1

            if not closed:
                # 閉じていないフェンスは横取りせず、そのまま fenced_code に委ねる。
                output.append(match.group(0))
                output.extend(body)
                continue

            output.append(self.md.htmlStash.store(_diagram_html(body)))

        return output


def _diagram_html(body: List[str]) -> str:
    """図の定義を ``<pre class="mermaid">`` に包む。

    mermaid.js は要素の textContent を読むため、``A --> B[<判定>]`` のような記述が
    HTML として解釈されないようエスケープする（表示時に元の文字へ戻る）。
    """
    return '<pre class="mermaid">' + html.escape("\n".join(body)) + "</pre>"


class MermaidExtension(Extension):
    def extendMarkdown(self, md) -> None:
        md.preprocessors.register(MermaidPreprocessor(md), "docmold_mermaid", PRIORITY)


def makeExtension(**kwargs):  # pragma: no cover - Markdown の慣例
    return MermaidExtension(**kwargs)
