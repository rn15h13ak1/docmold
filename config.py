"""プロファイル定義 (YAML) の読み込みと検証。

docmold の設定は「どんな表現があるか」の一覧に徹する。判定ロジックは持たず、
``profiles`` (構造 × 意味づけ × 見た目の組み合わせ) と ``themes`` (CSS 変数) だけを持つ。

読み込み順:
  1. 同梱の ``profiles.yaml``  — 既定のプロファイル定義 (常に読む)
  2. ユーザ設定 ``config.yaml`` — 1 に再帰マージ。差分だけ書けばよい

ユーザ設定の探索は ``CWD/config.yaml`` → ``docmold.py と同じディレクトリ/config.yaml``
の順。``--config`` で明示指定もできる。
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

try:
    import yaml
except ImportError as e:  # pragma: no cover - 依存が無い環境向けの案内
    raise ImportError("PyYAML is required. Install with: pip install pyyaml") from e

SCRIPT_DIR = Path(__file__).resolve().parent

#: 同梱の既定プロファイル定義。ユーザ設定はこの上に重なる。
BUNDLED_PROFILES_PATH = SCRIPT_DIR / "profiles.yaml"

#: すべてのプロファイルに共通で入れる Markdown 拡張。
BASE_EXTENSIONS = [
    "extra",        # tables / fenced_code / def_list / attr_list など
    "admonition",   # !!! note 形式の注意ボックス
    "sane_lists",
    "toc",
    "codehilite",
]

#: 既定プロファイル名 (front matter に type が無いときに使う)。
DEFAULT_PROFILE = "default"

#: 本文の生 HTML の扱い。"strict" = 許可リストで絞る / "none" = 素通し。
SANITIZE_MODES = ("strict", "none")

#: トップレベルで指定が無いときの既定。安全側に倒す。
DEFAULT_SANITIZE = "strict"


def parse_sanitize(value: Any, where: str) -> str:
    """``sanitize`` の指定を "strict" / "none" に正規化する。"""
    if value is None:
        return DEFAULT_SANITIZE
    if value is True:
        return "strict"
    if value is False:
        return "none"
    text = str(value).strip().lower()
    if text in SANITIZE_MODES:
        return text
    if text in ("off", "false", "no"):
        return "none"
    raise ConfigError(
        f"{where}.sanitize: {' / '.join(SANITIZE_MODES)} か true / false で指定してください"
        f" (実際: {value!r})"
    )


class ConfigError(ValueError):
    """設定ファイルに問題があるときに送出。"""


@dataclass(frozen=True)
class TocSettings:
    """目次の設定。``toc: false`` / ``toc: true`` / ``toc: {depth, numbering}``。"""

    enabled: bool = False
    depth: int = 3
    numbering: bool = False

    @classmethod
    def parse(cls, value: Any, where: str) -> "TocSettings":
        if value is None or value is False:
            return cls(enabled=False)
        if value is True:
            return cls(enabled=True)
        if isinstance(value, Mapping):
            unknown = set(value) - {"depth", "numbering"}
            if unknown:
                raise ConfigError(f"{where}.toc: 未知のキー: {sorted(unknown)}")
            try:
                depth = int(value.get("depth", 3))
            except (TypeError, ValueError):
                raise ConfigError(f"{where}.toc.depth: 整数で指定してください") from None
            if not 1 <= depth <= 6:
                raise ConfigError(f"{where}.toc.depth: 1〜6 で指定してください (実際: {depth})")
            return cls(enabled=True, depth=depth, numbering=bool(value.get("numbering", False)))
        raise ConfigError(f"{where}.toc: bool かマッピングで指定してください")


@dataclass(frozen=True)
class PrintSettings:
    """印刷 (PDF 化) 前提の設定。``@media print`` に効く。"""

    page_break_per_h1: bool = False
    page_break_per_h2: bool = False
    cover_page: bool = False

    _KNOWN = ("page_break_per_h1", "page_break_per_h2", "cover_page")

    @classmethod
    def parse(cls, value: Any, where: str) -> "PrintSettings":
        if not value:
            return cls()
        if not isinstance(value, Mapping):
            raise ConfigError(f"{where}.print: マッピングで指定してください")
        unknown = set(value) - set(cls._KNOWN)
        if unknown:
            raise ConfigError(f"{where}.print: 未知のキー: {sorted(unknown)}")
        return cls(**{key: bool(value.get(key, False)) for key in cls._KNOWN})


#: CDN 参照の既定 URL。再現性のためメジャーバージョンを固定する。
DEFAULT_MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"


@dataclass(frozen=True)
class MermaidSettings:
    """図の描画に使う mermaid.js の入手先。

    ``false``            無効（既定）
    ``true`` / bundled   同梱の assets/mermaid.min.js を埋め込む（外部参照ゼロを保つ）
    ``cdn``              既定の CDN を参照する（HTML は軽いが、閲覧時にインターネットが要る）
    ``{url: ...}``       指定した URL を参照する（社内にホスティングした場合など）
    """

    enabled: bool = False
    bundled: bool = True
    url: str = ""
    integrity: str = ""

    _KNOWN = ("source", "url", "integrity")

    @classmethod
    def parse(cls, value: Any, where: str) -> "MermaidSettings":
        if value is None or value is False:
            return cls()
        if value is True:
            return cls(enabled=True, bundled=True)

        if isinstance(value, str):
            keyword = value.strip().lower()
            if keyword in ("bundled", "embed", "local"):
                return cls(enabled=True, bundled=True)
            if keyword == "cdn":
                return cls(enabled=True, bundled=False, url=DEFAULT_MERMAID_URL)
            if keyword.startswith(("http://", "https://")):
                return cls(enabled=True, bundled=False, url=value.strip())
            raise ConfigError(
                f"{where}.mermaid: 'bundled' / 'cdn' / URL / true / false で指定してください"
                f" (実際: {value!r})"
            )

        if isinstance(value, Mapping):
            unknown = set(value) - set(cls._KNOWN)
            if unknown:
                raise ConfigError(f"{where}.mermaid: 未知のキー: {sorted(unknown)}")
            source = str(value.get("source", "cdn")).lower()
            url = str(value.get("url", "") or "")
            if source in ("bundled", "embed", "local"):
                if url:
                    raise ConfigError(f"{where}.mermaid: source: bundled に url は指定できません")
                return cls(enabled=True, bundled=True)
            if url and not url.startswith(("http://", "https://")):
                raise ConfigError(f"{where}.mermaid.url: http(s) の URL で指定してください")
            return cls(
                enabled=True,
                bundled=False,
                url=url or DEFAULT_MERMAID_URL,
                integrity=str(value.get("integrity", "") or ""),
            )

        raise ConfigError(f"{where}.mermaid: bool / 文字列 / マッピングで指定してください")


@dataclass(frozen=True)
class Theme:
    """見た目。CSS 変数として ``:root`` に流し込む。"""

    name: str
    variables: Dict[str, str] = field(default_factory=dict)

    def css_variables(self) -> str:
        """``--accent: #00529b;`` の形に展開する (キーの ``_`` は ``-`` に統一)。"""
        return "\n".join(
            f"  --{key.replace('_', '-')}: {value};"
            for key, value in self.variables.items()
        )


@dataclass(frozen=True)
class Profile:
    """テンプレート (構造) × ルール (意味づけ) × テーマ (見た目) の組み合わせ。"""

    name: str
    template: str = "article.html"
    theme: str = "corporate"
    toc: TocSettings = field(default_factory=TocSettings)
    rules: List[str] = field(default_factory=list)
    extensions: List[str] = field(default_factory=list)
    meta_header: List[str] = field(default_factory=list)
    print: PrintSettings = field(default_factory=PrintSettings)
    watermark: Optional[str] = None
    mermaid: MermaidSettings = field(default_factory=MermaidSettings)
    sanitize: str = DEFAULT_SANITIZE
    description: str = ""

    _KNOWN_KEYS = frozenset({
        "template", "theme", "toc", "rules", "extensions",
        "meta_header", "print", "watermark", "mermaid", "sanitize", "description",
    })

    @classmethod
    def parse(cls, name: str, value: Any,
              default_sanitize: str = DEFAULT_SANITIZE) -> "Profile":
        where = f"profiles.{name}"
        if value is None:
            value = {}
        if not isinstance(value, Mapping):
            raise ConfigError(f"{where}: マッピングで指定してください")
        unknown = set(value) - cls._KNOWN_KEYS
        if unknown:
            raise ConfigError(
                f"{where}: 未知のキー: {sorted(unknown)}"
                f" (使えるキー: {', '.join(sorted(cls._KNOWN_KEYS))})"
            )

        template = str(value.get("template", "article.html"))
        if "/" in template or "\\" in template or template.startswith("."):
            raise ConfigError(f"{where}.template: templates/ 直下のファイル名で指定してください")

        return cls(
            name=name,
            template=template,
            theme=str(value.get("theme", "corporate")),
            toc=TocSettings.parse(value.get("toc"), where),
            rules=_as_str_list(value.get("rules"), f"{where}.rules"),
            extensions=_as_str_list(value.get("extensions"), f"{where}.extensions"),
            meta_header=_as_str_list(value.get("meta_header"), f"{where}.meta_header"),
            print=PrintSettings.parse(value.get("print"), where),
            watermark=_optional_str(value.get("watermark")),
            mermaid=MermaidSettings.parse(value.get("mermaid"), where),
            sanitize=(
                parse_sanitize(value["sanitize"], where)
                if "sanitize" in value else default_sanitize
            ),
            description=str(value.get("description", "")),
        )

    @property
    def markdown_extensions(self) -> List[str]:
        """基本拡張 + プロファイル固有拡張。重複は除き、記述順を維持する。"""
        result: List[str] = []
        for ext in [*BASE_EXTENSIONS, *self.extensions]:
            if ext not in result:
                result.append(ext)
        return result


@dataclass(frozen=True)
class Config:
    """設定ファイル全体。"""

    profiles: Dict[str, Profile]
    themes: Dict[str, Theme]
    keywords: Dict[str, List[str]] = field(default_factory=dict)
    config_path: Optional[Path] = None

    def profile(self, name: str) -> Profile:
        """名前でプロファイルを引く。未定義なら ``KeyError``。"""
        return self.profiles[name]

    def theme_for(self, profile: Profile) -> Theme:
        try:
            return self.themes[profile.theme]
        except KeyError:
            raise ConfigError(
                f"profiles.{profile.name}: 未定義のテーマ '{profile.theme}'"
                f" (定義済み: {', '.join(sorted(self.themes)) or 'なし'})"
            ) from None

    @property
    def type_names(self) -> List[str]:
        """front matter の ``type:`` に書ける名前の一覧。"""
        return sorted(self.profiles)


def _as_str_list(value: Any, where: str) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    raise ConfigError(f"{where}: リストで指定してください")


def _optional_str(value: Any) -> Optional[str]:
    if value is None or value is False or value == "":
        return None
    return str(value)


def _deep_merge(base: Dict[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    """``override`` を ``base`` に再帰的に重ねる (``base`` は破壊しない)。

    マッピング同士はキー単位でマージし、それ以外 (リスト・スカラ) は置き換える。
    ``rules`` を差分ではなく丸ごと指定できるようにするため、リストは追記しない。
    """
    result = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(dict(result[key]), value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"{path}: YAML を解釈できません: {e}") from e
    except OSError as e:
        raise ConfigError(f"{path}: 読み込めません: {e}") from e
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: トップレベルはマッピングである必要があります")
    return raw


def build_config(raw: Mapping[str, Any], config_path: Optional[Path] = None) -> Config:
    """マージ済みの dict を検証して ``Config`` にする。"""
    unknown = set(raw) - {"profiles", "themes", "keywords", "sanitize"}
    if unknown:
        raise ConfigError(
            f"未知のトップレベルキー: {sorted(unknown)}"
            f" (使えるキー: keywords, profiles, sanitize, themes)"
        )

    # トップレベルの sanitize は全プロファイルの既定。種類ごとの指定が優先する。
    default_sanitize = parse_sanitize(raw.get("sanitize"), "")

    themes_raw = raw.get("themes") or {}
    if not isinstance(themes_raw, Mapping):
        raise ConfigError("themes: マッピングで指定してください")
    themes: Dict[str, Theme] = {}
    for name, value in themes_raw.items():
        if value is None:
            value = {}
        if not isinstance(value, Mapping):
            raise ConfigError(f"themes.{name}: マッピングで指定してください")
        themes[str(name)] = Theme(
            name=str(name),
            variables={str(k): str(v) for k, v in value.items()},
        )

    keywords_raw = raw.get("keywords") or {}
    if not isinstance(keywords_raw, Mapping):
        raise ConfigError("keywords: マッピングで指定してください")
    from rules import keywords as keyword_registry  # 循環 import 回避のため遅延 import

    missing_groups = keyword_registry.unknown_groups(keywords_raw)
    if missing_groups:
        raise ConfigError(
            f"keywords: 未知のグループ: {sorted(missing_groups)}"
            f" (使えるグループ: {', '.join(sorted(keyword_registry.GROUPS))})"
        )
    keyword_overrides = {
        str(group): _as_str_list(words, f"keywords.{group}")
        for group, words in keywords_raw.items()
    }
    for group, words in keyword_overrides.items():
        if not words:
            raise ConfigError(f"keywords.{group}: 空にはできません（検出できなくなります）")

    profiles_raw = raw.get("profiles") or {}
    if not isinstance(profiles_raw, Mapping):
        raise ConfigError("profiles: マッピングで指定してください")
    profiles = {
        str(name): Profile.parse(str(name), value, default_sanitize)
        for name, value in profiles_raw.items()
    }

    if DEFAULT_PROFILE not in profiles:
        raise ConfigError(f"profiles に '{DEFAULT_PROFILE}' が必要です (type 未指定時に使います)")

    config = Config(profiles=profiles, themes=themes,
                    keywords=keyword_overrides, config_path=config_path)
    # テーマ未定義・ルール未登録は読み込み時点で弾く (変換の途中で落とさない)。
    from rules import unknown_rules  # 循環 import 回避のため遅延 import

    for profile in profiles.values():
        config.theme_for(profile)
        missing = unknown_rules(profile.rules)
        if missing:
            raise ConfigError(
                f"profiles.{profile.name}.rules: 未登録のルール: {sorted(missing)}"
                f" (--list-rules で一覧を確認できます)"
            )
    return config


def find_user_config(explicit: Optional[str], default_search_dir: Path = SCRIPT_DIR) -> Optional[Path]:
    """ユーザ設定 config.yaml の場所を決める。無ければ None。"""
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ConfigError(f"設定ファイルが見つかりません: {path}")
        return path

    for candidate in (Path.cwd() / "config.yaml", default_search_dir / "config.yaml"):
        if candidate.is_file():
            return candidate
    return None


def load_config(explicit: Optional[str] = None,
                default_search_dir: Path = SCRIPT_DIR) -> Config:
    """同梱の profiles.yaml を読み、ユーザ設定があれば重ねて ``Config`` を返す。"""
    if not BUNDLED_PROFILES_PATH.is_file():
        raise ConfigError(f"同梱の既定設定が見つかりません: {BUNDLED_PROFILES_PATH}")

    raw = _load_yaml(BUNDLED_PROFILES_PATH)
    user_path = find_user_config(explicit, default_search_dir)
    if user_path is not None:
        raw = _deep_merge(raw, _load_yaml(user_path))
    return build_config(raw, config_path=user_path or BUNDLED_PROFILES_PATH)
