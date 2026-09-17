"""Markdown → HTML 変換パイプライン。

    front matter 分離
      → type からプロファイル決定（未指定なら default）
      → Markdown → HTML（拡張はプロファイル依存）
      → ② ルール層: DOM 後処理
      → ① テンプレート描画 + ③ テーマ CSS 埋め込み
    自己完結 HTML（1 ファイル）

種類の判定は **書き手が明示した種類だけ** を見る。パス名や本文からの自動判定は
誤判定で事故るうえ保守コストが乗るため行わない。
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import markdown
    from markdown.extensions.toc import slugify_unicode
except ImportError as e:  # pragma: no cover - 依存が無い環境向けの案内
    raise ImportError("Markdown is required. Install with: pip install markdown") from e

try:
    from bs4 import BeautifulSoup
except ImportError as e:  # pragma: no cover
    raise ImportError("beautifulsoup4 is required. Install with: pip install beautifulsoup4") from e

from assets import embed_images
from config import DEFAULT_PROFILE, Config, Profile
from frontmatter import meta_to_text, split_front_matter
from mermaid_ext import MermaidExtension
from renderer import render
from rules import DERIVED_KEY, apply_rules, keywords, take_warnings
from sanitize import sanitize
from rules.common import HEADING_TAGS, add_class, heading_level, wrap_section

#: 本文からタイトルを拾えなかったときの表示名。
FALLBACK_TITLE = "(無題)"

#: front matter で常に意味を持つキー。
RESERVED_META_KEYS = ("type", "title")

#: 打ち間違いとみなす類似度。下げると無関係なキーまで指摘し始める。
TYPO_CUTOFF = 0.75

#: 文書間リンクとして書き換える拡張子（変換後は .html になる）。
LINK_EXTS = (".md", ".markdown")

#: 書き換えないリンク。外部参照とページ内アンカー。
_EXTERNAL_LINK_RE = re.compile(r"\A(?:[a-z][a-z0-9+.-]*:|//|#)", re.IGNORECASE)


class ConversionError(RuntimeError):
    """変換に失敗したときに送出。"""


@dataclass
class ConversionResult:
    """1 ファイル分の変換結果。"""

    html: str
    title: str
    profile_name: str
    meta: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    source_path: Optional[Path] = None


def resolve_profile(config: Config, meta: Dict[str, Any],
                    type_override: Optional[str] = None) -> tuple:
    """使用するプロファイルと警告を決める。

    未知の type は黙って default に落とさず、警告のうえ default で処理する
    （タイプミスに気づけないまま変換されるのを防ぐ）。
    """
    warnings: List[str] = []
    requested = type_override or meta.get("type") or DEFAULT_PROFILE
    requested = str(requested).strip() or DEFAULT_PROFILE

    if requested not in config.profiles:
        warnings.append(
            f"未知の type '{requested}' — {DEFAULT_PROFILE} で処理します"
            f" (指定できる type: {', '.join(config.type_names)})"
        )
        requested = DEFAULT_PROFILE

    return config.profile(requested), warnings


def convert_text(text: str, config: Config, *,
                 type_override: Optional[str] = None,
                 source_path: Optional[Path] = None,
                 title_override: Optional[str] = None) -> ConversionResult:
    """Markdown 文字列を自己完結 HTML に変換する。"""
    meta, body = split_front_matter(text)
    profile, warnings = resolve_profile(config, meta, type_override)

    extensions = list(profile.markdown_extensions)
    if profile.mermaid.enabled:
        # ```mermaid を codehilite に食われる前に横取りする。
        extensions.append(MermaidExtension())

    md = markdown.Markdown(
        extensions=extensions,
        extension_configs=_extension_configs(profile),
    )
    html = md.convert(body)

    # 検出語は設定で差し替えられる。ルールを適用する前に有効化する。
    keywords.use(config.keywords)
    warnings.extend(_check_meta_typos(meta, profile))

    soup = BeautifulSoup(html, "html.parser")

    # 生 HTML の絞り込みは、本文だけが対象。ルール層やテンプレートが作る要素は
    # docmold 自身の生成物なので、この後に組み立てる。
    if profile.sanitize == "strict":
        removed = sanitize(soup, profile.allow_schemes)
        if removed:
            warnings.append(
                f"本文の HTML を {removed} 箇所ほど除きました"
                f"（sanitize: strict。素通しにするには sanitize: false）"
            )

    _rewrite_document_links(soup)
    _wrap_sections(soup)
    apply_rules(profile.rules, soup, meta)
    warnings.extend(take_warnings(meta))

    # 目次はルール適用後の DOM から作るため、画像埋め込みより先に確定させる。
    toc = _build_toc(soup, profile)
    base_dir = source_path.parent if source_path is not None else None
    warnings.extend(embed_images(soup, base_dir))

    title = title_override or _resolve_title(meta, soup, source_path)
    derived = meta.get(DERIVED_KEY) or {}

    return ConversionResult(
        html=render(
            config=config,
            profile=profile,
            content=str(soup),
            title=title,
            meta=meta,
            derived=derived,
            toc=toc,
            meta_header=_build_meta_header(profile, meta),
            warnings=warnings,
        ),
        title=title,
        profile_name=profile.name,
        meta=meta,
        warnings=warnings,
        source_path=source_path,
    )


def convert_file(path: Path, config: Config, *,
                 type_override: Optional[str] = None) -> ConversionResult:
    """``.md`` ファイルを読み込んで変換する。"""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # Windows で作られた .md は cp932 のことがある。
        try:
            text = path.read_text(encoding="cp932")
        except (UnicodeDecodeError, LookupError) as e:
            raise ConversionError(f"{path}: 文字コードを判別できません (utf-8 / cp932): {e}") from e
    except OSError as e:
        raise ConversionError(f"{path}: 読み込めません: {e}") from e

    return convert_text(text, config, type_override=type_override, source_path=path)


def _extension_configs(profile: Profile) -> Dict[str, Dict[str, Any]]:
    configs: Dict[str, Dict[str, Any]] = {
        # CDN も外部 CSS も使えない前提なので、色は Pygments の生成 CSS で埋め込む。
        "codehilite": {"guess_lang": False, "noclasses": False},
        # 既定の slugify は日本語見出しを空にしてしまい、アンカーが _1 / _2 になる。
        # 見出し文字列を残す slugify_unicode を使い、他文書からもリンクできるようにする。
        "toc": {
            "toc_depth": profile.toc.depth,
            "anchorlink": False,
            "permalink": False,
            "slugify": slugify_unicode,
        },
    }
    return {name: cfg for name, cfg in configs.items() if name in profile.markdown_extensions}


def _check_meta_typos(meta: Dict[str, Any], profile: Profile) -> List[str]:
    """front matter のキーの打ち間違いらしきものを指摘する。

    未知のキーをすべて警告すると、覚え書きとして自由に書いた項目まで指摘してしまう。
    「意味を持つキーによく似ているのに一致しない」ものだけを対象にする。
    """
    known = _known_meta_keys(profile)
    warnings: List[str] = []

    for key in meta:
        if key.startswith("_") or key in known:
            continue
        matches = difflib.get_close_matches(key, sorted(known), n=1, cutoff=TYPO_CUTOFF)
        # 似ているキーが同じ front matter に既にあるなら、書き分けているだけ。
        if matches and matches[0] not in meta:
            warnings.append(
                f"front matter の '{key}' は '{matches[0]}' の打ち間違いではありませんか"
            )
    return warnings


def _known_meta_keys(profile: Profile) -> set:
    """そのプロファイルで意味を持つ front matter のキー。"""
    return {
        *RESERVED_META_KEYS,
        *profile.meta_header,
        *keywords.get("index_date"),
        *keywords.get("severity"),
    }


def _rewrite_document_links(soup: BeautifulSoup) -> None:
    """``[設計書](設計書.md)`` のような文書間リンクを ``.html`` に向け直す。

    ディレクトリを一括変換すると入力の階層をそのまま出力に写すため、相対リンクは
    拡張子だけ替えれば通る。書き換えないと、配布した HTML のリンクが軒並み切れる。

    外部 URL（``http:`` ``mailto:`` など）とページ内アンカー（``#...``）は触らない。
    リンク先が実際に変換されるかまでは見ない（入力に含まれない .md への参照は
    書き換えても切れたままだが、含まれる場合のほうが圧倒的に多いため）。
    """
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        if not href or _EXTERNAL_LINK_RE.match(href):
            continue

        # フラグメントとクエリは温存する（設計書.md#概要 → 設計書.html#概要）。
        path, separator, suffix = _split_link(href)
        if path.lower().endswith(LINK_EXTS):
            base = path.rsplit(".", 1)[0]
            link["href"] = f"{base}.html{separator}{suffix}"


def _split_link(href: str) -> tuple:
    """``href`` を (パス, 区切り文字, 残り) に分ける。区切りが無ければ ("", "")。"""
    for separator in ("#", "?"):
        if separator in href:
            path, suffix = href.split(separator, 1)
            return path, separator, suffix
    return href, "", ""


def _wrap_sections(soup: BeautifulSoup) -> None:
    """トップレベルの見出しごとに ``<section>`` で包む。

    ダッシュボードのカード配置や ``@media print`` の改ページを、テンプレート側の
    CSS だけで書けるようにするための構造の正規化。ルールより先に行う。
    """
    levels = sorted({heading_level(h) for h in soup.find_all(HEADING_TAGS)} - {0})
    if not levels:
        return
    top = levels[0]
    for heading in list(soup.find_all(f"h{top}")):
        if heading.parent is not soup:
            continue
        section = wrap_section(soup, heading, "dm-section", f"dm-section--h{top}")
        if heading.get("id"):
            section["data-heading-id"] = heading["id"]


def _build_toc(soup: BeautifulSoup, profile: Profile) -> List[Dict[str, Any]]:
    """目次の項目を DOM から組み立てる。

    Markdown 拡張の ``md.toc`` ではなく、ルール適用後の DOM から作る。
    ルールが見出しを足したり消したりしても目次と本文がずれない。
    """
    if not profile.toc.enabled:
        return []

    items: List[Dict[str, Any]] = []
    for heading in soup.find_all(HEADING_TAGS):
        level = heading_level(heading)
        if level > profile.toc.depth:
            continue
        anchor = heading.get("id")
        if not anchor:
            anchor = f"dm-heading-{len(items) + 1}"
            heading["id"] = anchor
        items.append({"level": level, "text": _heading_text(heading), "anchor": anchor})

    if profile.toc.numbering:
        _number_toc(items, soup)
    return items


#: 見出しに差し込む UI 要素。目次の文言からは除く。
UI_CLASSES = ("dm-step__number", "dm-step__check", "dm-heading__number",
              "dm-topic__number")


def _heading_text(heading: Any) -> str:
    """見出しの文言。ルールが差し込んだ番号やチェック欄は含めない。

    ``<h2><span class="dm-step__number">1</span>手順 1: 事前確認<label …>完了</label></h2>``
    のような見出しから ``手順 1: 事前確認`` だけを取り出す。
    """
    parts = [
        str(node) for node in heading.find_all(string=True)
        if not node.find_parent(class_=list(UI_CLASSES))
    ]
    return "".join(parts).strip()


def _number_toc(items: List[Dict[str, Any]], soup: BeautifulSoup) -> None:
    """章番号 (1. / 1.1 / 1.1.1) を目次と見出しの両方に振る。"""
    counters: List[int] = []
    for item in items:
        level = item["level"]
        if len(counters) < level:
            counters.extend([0] * (level - len(counters)))
        else:
            del counters[level:]
        counters[level - 1] += 1
        number = ".".join(str(n) for n in counters[:level])
        item["number"] = number

        heading = soup.find(id=item["anchor"])
        if heading is not None:
            label = soup.new_tag("span")
            add_class(label, "dm-heading__number")
            label.string = number
            heading.insert(0, label)


def _build_meta_header(profile: Profile, meta: Dict[str, Any]) -> List[Dict[str, str]]:
    """``meta_header`` に並べたキーを、front matter の値と組にして返す。"""
    rows = []
    for key in profile.meta_header:
        text = meta_to_text(meta.get(key))
        if text:
            rows.append({"label": key, "value": text})
    return rows


def _resolve_title(meta: Dict[str, Any], soup: BeautifulSoup,
                   source_path: Optional[Path]) -> str:
    """front matter の title → 最初の見出し → ファイル名 の順で決める。"""
    title = meta_to_text(meta.get("title"))
    if title:
        return title

    heading = soup.find(HEADING_TAGS)
    if heading is not None:
        # 章番号や完了チェックはルールが差し込んだ UI なので、タイトルに含めない
        # （spec で「1概要」のようになるのを防ぐ）。
        text = _heading_text(heading)
        if text:
            return text

    return source_path.stem if source_path is not None else FALLBACK_TITLE
