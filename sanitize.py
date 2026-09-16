"""本文の生 HTML を安全な範囲に絞る（許可リスト方式）。

Markdown の仕様では生の HTML はそのまま通る。docmold の出力はファイルサーバや
メールで配布されるため、他の人が書いた ``.md`` に ``<script>`` が混ざっていると、
それを配ることになる。

**許可した要素・属性だけを残し、それ以外は落とす。** 禁止リスト方式は、新しい書き方が
出てくるたびに漏れるため採らない。

適用するのは **Markdown が生成した本文だけ**。ルール層やテンプレートが作る要素
（チェックボックス、コピーボタン、Mermaid の読み込み）は docmold 自身の生成物なので、
サニタイズより後に組み立てる。
"""
from __future__ import annotations

import re
from typing import Any, Dict, FrozenSet

#: 残す要素。Markdown（extra / admonition / codehilite / toc）が生成するものと、
#: 文書内で手書きされても無害なものを含む。
ALLOWED_TAGS: FrozenSet[str] = frozenset({
    # 文章
    "p", "br", "hr", "span", "div", "blockquote", "q", "cite", "pre",
    "em", "strong", "b", "i", "u", "s", "small", "mark", "sub", "sup",
    "del", "ins", "abbr", "code", "kbd", "samp", "var",
    # 見出し
    "h1", "h2", "h3", "h4", "h5", "h6",
    # リスト
    "ul", "ol", "li", "dl", "dt", "dd",
    # 表
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col",
    # 図・リンク
    "a", "img", "figure", "figcaption",
    # 折りたたみ
    "details", "summary",
})

#: 中身ごと消す要素。文字として残すと、かえって読みにくくなるもの。
DROP_TAGS: FrozenSet[str] = frozenset({
    "script", "style", "iframe", "object", "embed", "applet", "noscript",
    "template", "base", "link", "meta", "frame", "frameset",
    "form", "input", "button", "select", "option", "textarea",
    "svg", "math", "canvas", "audio", "video", "source", "track", "map", "area",
})

#: どの要素にも許す属性。
GLOBAL_ATTRS: FrozenSet[str] = frozenset({"class", "id", "title", "lang", "dir"})

#: 要素ごとに許す属性。
TAG_ATTRS: Dict[str, FrozenSet[str]] = {
    "a": frozenset({"href"}),
    "img": frozenset({"src", "alt", "width", "height"}),
    "th": frozenset({"colspan", "rowspan", "scope", "style"}),
    "td": frozenset({"colspan", "rowspan", "style"}),
    "col": frozenset({"span"}),
    "colgroup": frozenset({"span"}),
    "ol": frozenset({"start", "type"}),
    "details": frozenset({"open"}),
    "time": frozenset({"datetime"}),
}

#: 表の桁揃えは Markdown が style で出すため、この形だけ通す。
ALLOWED_STYLE_RE = re.compile(r"\A\s*text-align:\s*(left|center|right)\s*;?\s*\Z", re.IGNORECASE)

#: URL として危険なスキーム。相対パス（設計書.md）はスキームを持たないので通る。
DANGEROUS_SCHEME_RE = re.compile(r"\A\s*(javascript|vbscript|data|file|about)\s*:", re.IGNORECASE)

#: 画像の埋め込みに使う data URI だけは例外として通す。
SAFE_DATA_URI_RE = re.compile(r"\Adata:image/(png|jpe?g|gif|svg\+xml|webp|bmp|x-icon);", re.IGNORECASE)


def sanitize(soup: Any) -> int:
    """本文を安全な範囲に絞る。落とした箇所の数を返す。

    - 許可していない要素は、中身を残して外す（``<font>`` など）
    - ``script`` のように中身ごと消したほうがよいものは、まとめて削除する
    - 許可していない属性（``onerror`` ``style`` など）は外す
    - ``javascript:`` などのスキームを持つ ``href`` / ``src`` は外す
    """
    removed = 0

    for tag in soup.find_all(list(DROP_TAGS)):
        tag.decompose()
        removed += 1

    for tag in soup.find_all(True):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            removed += 1
            continue
        removed += _clean_attributes(tag)

    return removed


def _clean_attributes(tag: Any) -> int:
    allowed = GLOBAL_ATTRS | TAG_ATTRS.get(tag.name, frozenset())
    removed = 0

    for name in list(tag.attrs):
        if name.lower() not in allowed:
            del tag[name]
            removed += 1
            continue
        if name.lower() == "style" and not ALLOWED_STYLE_RE.match(str(tag[name])):
            del tag[name]
            removed += 1

    for name in ("href", "src"):
        value = str(tag.get(name, "")).strip()
        if value and DANGEROUS_SCHEME_RE.match(value) and not SAFE_DATA_URI_RE.match(value):
            del tag[name]
            removed += 1

    return removed
