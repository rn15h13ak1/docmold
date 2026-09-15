# docmold

Markdown を、**内容の種類ごとに表現を変えた自己完結 HTML** に変換する CLI ツール。

議事録・作業手順書・障害報告・設計書・週次報告を、それぞれに合った構造 / 意味づけ / 見た目で出力します。
出力は CSS・JS・画像を埋め込んだ 1 ファイルで、外部参照を持ちません（閉域ネットワーク / CDN 不可の前提）。

## 主要機能

- **種類ごとの表現切り替え**: front matter の `type:` 1 行で、テンプレート・ルール・テーマがまとめて切り替わる
- **3 層分離**: 構造（テンプレート）/ 意味づけ（ルール）/ 見た目（テーマ）を独立に組み合わせる
- **YAML 駆動**: 種類の追加は「YAML 数行 + 必要ならルール関数 1 つ」。判定ロジックは設定に持たない
- **完全自己完結 HTML**: CSS / JS / 画像（base64）を 1 ファイルに埋め込み、外部参照ゼロ
- **印刷（PDF 化）前提**: 手順書は見出しごとに改ページ、設計書は表紙を 1 ページ目に
- **一括変換 + 索引**: ディレクトリ再帰と索引 HTML の生成

---

## 目次

**入門**
1. [クイックスタート](#クイックスタート)
2. [動作要件](#動作要件)

**使い方ガイド**
3. [メニューから実行する](#1-メニューから実行する)
4. [種類を指定する](#2-種類を指定する)
5. [一括変換する](#3-一括変換する)
6. [表現を調整する](#4-表現を調整する)
7. [種類を追加する](#5-種類を追加する)
8. [PDF 化する](#6-pdf-化する)

**リファレンス**
9. [同梱の種類](#同梱の種類)
10. [CLI オプション一覧](#cli-オプション一覧)
11. [出力先](#出力先)
12. [設定ファイル](#設定ファイル)
13. [ルール一覧](#ルール一覧)
14. [front matter のキー](#front-matter-のキー)
15. [Exit code](#exit-code)
16. [既知の制約](#既知の制約)
17. [ファイル構成](#ファイル構成)

**開発者向け**
18. [設計方針](#設計方針)
19. [テスト](#テスト)
20. [変更履歴](#変更履歴)

---

## クイックスタート

**メニューから使う**（CLI オプションを覚えなくてよい）:

```cmd
:: menu.bat をダブルクリック、またはコマンドから
cd C:/tools/docmold
menu.bat
```

**CLI から使う**:

```cmd
:: 1. Anaconda Prompt（通常権限）で展開先に移動
cd C:/tools/docmold

:: 2. 指定できる種類を確認
python docmold.py --list-types

:: 3. .md の先頭に種類を書いて変換
python docmold.py 議事録.md
:: → C:/tools/docmold/out/20260914-213045/議事録.html
```

出力先は **docmold 自身の `out/` 配下に、実行日時のフォルダを作って** その中に出します
（詳しくは [出力先](#出力先)）。

変換対象の `.md`：

```markdown
---
type: minutes
title: 定例会 議事録
日時: 2026-09-14 10:00-11:00
出席者: [山田太郎, 鈴木花子]
---

## 決定事項

- 本番切替は 10/18 に実施する。

## ToDo

- [ ] 手順書の作成 担当: 鈴木
```

`examples/` に 6 種類のサンプルがあります。まとめて出力して見比べられます：

```cmd
python docmold.py examples -o out --index
```

---

## 動作要件

- **Python 3.9 以上**
- 依存パッケージはすべて **Anaconda 同梱**

| パッケージ | 用途 |
| --- | --- |
| `markdown` | Markdown → HTML |
| `jinja2` | テンプレート描画 |
| `pyyaml` | front matter / 設定ファイル |
| `beautifulsoup4` | ルール層の DOM 後処理 |
| `pygments` | コードハイライト（無い場合は色なしで動作） |

Anaconda 以外の環境では:

```bash
pip install -r requirements.txt
```

**依存は「実行に使う Python」に入っている必要があります。** 別のツールの仮想環境や、
依存を入れていない Python で起動すると、次の案内が出て終了コード 2 で止まります。

```
必要なライブラリが入っていません: Markdown, Jinja2, beautifulsoup4

  実行中の Python: /path/to/other-tool/.venv/bin/python

次のいずれかで解決できます。
  1) この Python に入れる
     /path/to/other-tool/.venv/bin/python -m pip install -r /path/to/docmold/requirements.txt
  2) 依存が入っている Python で実行する
```

どの Python で動いているかが表示されるので、取り違えていないか確認してください。

---

## 使い方ガイド

### 1. メニューから実行する

CLI オプションを覚えなくても、番号を選ぶだけで実行できます。

```cmd
:: Windows はこれをダブルクリック
menu.bat

:: コマンドから起動する場合
python menu.py
```

```
============================================================
  docmold（Markdown → 自己完結 HTML）
============================================================
  設定: C:/tools/docmold/profiles.yaml（6 種類）

============================================================
  操作を選択
============================================================
  1. 変換する ― Markdown を自己完結 HTML に変換する ←前回
  2. 種類の一覧 ― front matter の type に書ける名前を表示する
  3. ルールの一覧 ― 種類ごとの意味づけ（後処理）を表示する
------------------------------------------------------------
  0. 終了
============================================================
```

「変換する」を選ぶと、変換対象 → 種類 → 出力先 → 索引の有無 → 実行モードの順に尋ねます。

- **変換対象** は `.md` かディレクトリ。Windows のドラッグ＆ドロップで付く引用符は自動で外します
- **種類** は「front matter に従う」が既定。別の表現で出したいときだけ上書きを選びます
- **出力先** は既定（`docmold/out/<日時>/`）か、場所の指定かを選びます
- **索引** はディレクトリを指定したときだけ尋ねます
- **実行モード** で「検証のみ」を選ぶと `--dry-run` 相当（HTML を書き出しません）
- 変換後に出力先をエクスプローラ / Finder で開けます

入力値は `~/.docmold_menu.json` に記憶され、次回の既定値になります。

ランチャーから起動する運用にも、この `menu.py` をそのまま呼び出せます。

> 無人実行（バッチ・タスクスケジューラ）ではメニューではなく `docmold.py` を直接呼んでください。
> その際は `--strict` を付けると、警告を取りこぼしません（下記）。

### 2. 種類を指定する

種類は **書き手が明示したものだけ** を見ます。パス名や本文からの自動判定は行いません
（誤判定で事故るうえ、ルールの保守コストが乗るため）。

**front matter に書く**（基本）:

```markdown
---
type: incident
---
```

**CLI で上書きする**（既存の `.md` を書き換えずに別表現で出したいとき）:

```cmd
python docmold.py 手順.md --type procedure
```

**指定しない場合**は `default`（汎用テンプレート・目次なし）で変換されます。

> 未知の `type` が書かれていた場合は、黙って `default` に落とさず **警告を出したうえで `default` で処理** します。
> タイプミスに気づけないまま変換されるのを防ぐためです。

### 3. 一括変換する

ディレクトリを渡すと `.md` / `.markdown` を再帰的に変換し、階層を保って出力します。

```cmd
:: docs/ 配下をすべて変換し、索引 HTML も作る
python docmold.py docs --index
```

```
docs/                          out/20260914-213045/
├── 定例.md          →         ├── 定例.html
├── 障害/                      ├── 障害/
│   └── 0910.md      →         │   └── 0910.html
└── 設計.md          →         ├── 設計.html
                               └── index.html   ← --index で生成
```

索引 HTML はタイトル・種類・元ファイルの一覧で、本体と同じく自己完結 1 ファイルです。

**文書間のリンクはそのまま繋がります。** `[設計書](設計書.md)` のような相対リンクは
`.html` に書き換えられ、入力の階層を出力に写すため、リンク先も同じ位置関係に出力されます。
外部 URL（`https://` `mailto:`）とページ内アンカー（`#節`）は書き換えません。

> リンク先が変換対象に含まれるかまでは確認しません。入力に含まれない `.md` への参照は、
> 書き換えても切れたままです。

### 4. 表現を調整する

同梱の定義を変えたいときは `config.yaml` に **差分だけ** 書きます。

```cmd
copy config.example.yaml config.yaml
```

```yaml
profiles:
  incident:
    watermark: false      # 確定版なので DRAFT 透かしを消す
  spec:
    toc:
      depth: 4            # 目次を 4 階層まで

themes:
  corporate:
    accent: "#006c4b"     # 自社色に差し替え
```

同梱の `profiles.yaml` に再帰マージされるため、書かなかったキーは既定のまま残ります。
`profiles.yaml` は直接編集しないでください（ツール更新で上書きされます）。

### 5. 種類を追加する

**表現の組み合わせを変えるだけなら YAML 数行** で済みます。

```yaml
profiles:
  review:
    description: レビュー記録
    template: article.html        # 既存テンプレートを再利用
    theme: corporate
    toc: true
    rules: [todo_checklist, status_badge]
    meta_header: [対象, レビュー日, 参加者]
```

**新しい意味づけが要るとき** は、ルール関数を 1 つ足します。

```python
# rules/review.py
from rules import rule
from rules.common import add_class, find_headings

@rule("review_severity")
def review_severity(soup, meta):
    """「指摘」節の見出しに重要度クラスを付ける。"""
    for heading in find_headings(soup, ["指摘"]):
        add_class(heading, "dm-review-finding")
```

`rules/__init__.py` の末尾の import に `review` を足せば、`--list-rules` に出て YAML から使えます。

### 6. PDF 化する

記録として残す場合は、ブラウザの印刷 → PDF 保存を使います。`@media print` を用意済みです。

| 種類 | 印刷時の挙動 |
| --- | --- |
| `procedure` | 見出し（手順）ごとに改ページ。コピーボタン・画面用の注記は印刷されない |
| `spec` | 表紙が単独で 1 ページ目。章ごとに改ページ |
| `incident` | DRAFT 透かしを全ページ中央に薄く配置 |
| 共通 | 手順カード・サマリカード・表の行がページ境界で分断されない |

ブラウザの印刷設定で「背景のグラフィック」を有効にしてください（バッジや見出しの色が出ます）。

---

## 同梱の種類

| type | 構造 | 意味づけ | 見た目 |
| --- | --- | --- | --- |
| `default` | 汎用・目次なし | なし | 標準テーマ |
| `minutes` | 冒頭に日時・出席者のメタ表、目次あり | ToDo をチェックボックス化、担当者をバッジ化、決定事項を強調 | 標準テーマ |
| `procedure` | 手順ごとにカード、進捗チェック欄 | 手順の自動採番、コマンドにコピーボタン、切戻し手順を強調 | 見出しごとに改ページ |
| `incident` | 冒頭にサマリカード（発生 / 復旧 / 影響範囲 / 重要度） | 時系列表をタイムライン表示、重要度バッジ | 警告色テーマ、DRAFT 透かし |
| `spec` | 表紙 + 章番号付き目次 + 図表一覧 | 図表番号の自動採番、相互参照リンク | 標準テーマ、印刷最適化 |
| `weekly` | カードレイアウト | ステータスバッジ、進捗バー | 標準テーマ |

一覧は `python docmold.py --list-types` でも確認できます。

---

## CLI オプション一覧

```
python docmold.py [入力...] [オプション]
```

| オプション | 説明 |
| --- | --- |
| `入力` | `.md` ファイル、またはそれを含むディレクトリ（複数可、ディレクトリは再帰） |
| `-o`, `--output` | 出力先。入力が 1 ファイルで `.html` を指定したときだけファイル扱い（省略時は [出力先](#出力先) を参照） |
| `-t`, `--type` | front matter の `type` を上書き |
| `-c`, `--config` | 設定ファイルのパス（default: `CWD/config.yaml` → `docmold.py と同じディレクトリ/config.yaml`） |
| `--index` | 出力ディレクトリに索引 HTML を生成 |
| `--list-types` | 指定できる種類の一覧を表示して終了 |
| `--list-rules` | 登録済みルールの一覧を表示して終了 |
| `--dry-run` | 変換の検証のみ。HTML は書き出さない |
| `--strict` | 警告があれば失敗扱いにする（終了コード 1） |
| `-v`, `--verbose` | 1 件ごとの変換結果を出力 |
| `-q`, `--quiet` | 警告以外の進捗を抑制 |

### 警告を取りこぼさない（`--strict`）

`type` のタイプミスや画像の欠落は警告として表示されますが、既定では**終了コードは 0** です。
バッチやタスクスケジューラで回すと誰も気づきません。`--strict` を付けると失敗扱いになります。

```
$ docmold.py docs -o out --strict
警告: docs/定例.md: 未知の type 'minuets' — default で処理します (指定できる type: ...)
--strict: 警告が 1 件あるため失敗として扱います。
$ echo $?
1
```

失敗扱いでも**変換結果は書き出します**。何が起きたかを出力で確認できるようにするためです。

---

## 出力先

### 既定（`-o` を付けない場合）

**docmold.py と同じディレクトリの `out/` 配下に、実行日時のフォルダを作って** その中に出力します。

```
C:/tools/docmold/out/
├── 20260914-213045/      ← 1 回目の実行
│   ├── 定例.html
│   └── index.html
└── 20260914-224512/      ← 2 回目の実行
    └── 障害報告.html
```

- **起動位置に依存しません。** メニューをどこから起動しても、バッチをどのフォルダで実行しても同じ `out/` に出ます
- **実行ごとにフォルダが分かれます。** 複数回実行しても結果が混ざらず、前回の出力が上書きされることもありません
- フォルダ名は `YYYYMMDD-HHMMSS`
- 古い実行結果は自動では消えません。不要になったらフォルダごと削除してください

### `-o` を指定した場合

指定したパスを**そのまま**使います。タイムスタンプのフォルダは作りません。
バッチやタスクスケジューラから決まった場所に出す用途を想定しています。

| 実行 | 出力 |
| --- | --- |
| `docmold.py docs -o dist` | `dist/` 配下（`docs/` の階層を維持） |
| `docmold.py memo.md -o report.html` | `report.html` |
| `docmold.py docs -o //server/share/html --index` | 共有フォルダ直下に索引ごと出力 |

相対パスは**実行時のカレントディレクトリ基準**です。ファイル扱いになるのは
「入力が 1 ファイル」かつ「拡張子が `.html` / `.htm`」のときだけで、
それ以外はディレクトリ名として扱われます。

ディレクトリを渡した場合は入力の階層を保ちます（`docs/sub/b.md` → `<出力先>/sub/b.html`）。
索引 HTML（`--index`）は出力ディレクトリ直下の `index.html` です。

### 出力先が重なる場合

別々のディレクトリにある同名ファイルを個別に指定すると、出力先がぶつかります。
この場合は名前をずらして**両方残し**、警告を出します。

```
$ docmold.py a/doc.md b/doc.md -o out
警告: 出力先が重なるため名前を変えました: b/doc.md → doc-b.html（doc.html は先に変換したファイルが使用）

$ ls out
doc.html  doc-b.html
```

2 番目以降に親ディレクトリ名を付けます。それでも重なる場合は連番になります。
ディレクトリを渡した場合は階層を保つため、元から衝突しません。

---

## 設定ファイル

読み込み順は **同梱 `profiles.yaml` → ユーザ `config.yaml`（再帰マージ）**。

`profiles.<type>` に書けるキー:

| キー | 型 | 説明 |
| --- | --- | --- |
| `template` | 文字列 | `templates/` 直下の HTML ファイル名（構造） |
| `theme` | 文字列 | `themes.<name>`（見た目 = CSS 変数） |
| `toc` | bool / マッピング | `false` / `true` / `{depth: 1-6, numbering: bool}` |
| `rules` | リスト | 意味づけの後処理。**並べた順に適用される** |
| `extensions` | リスト | 基本拡張に追加する Markdown 拡張 |
| `meta_header` | リスト | 冒頭のメタ表に出す front matter のキーと順序 |
| `print` | マッピング | `page_break_per_h1` / `page_break_per_h2` / `cover_page` |
| `watermark` | 文字列 / `false` | 透かし文字列（例: `DRAFT`） |
| `mermaid` | bool | `assets/mermaid.min.js` を埋め込む |
| `description` | 文字列 | `--list-types` に出す説明 |

`themes.<name>` の各キーは CSS 変数として `:root` に流し込まれます（`accent_weak` → `--accent-weak`）。
テーマの色を増やしたい場合は、キーを足して `themes/*.css` から参照してください。

設定ファイルに置くのは **プロファイルの定義だけ** です。判定ロジックを持たないため、
YAML は「どんな表現があるか」の一覧として読める状態に保たれます。

---

## ルール一覧

`python docmold.py --list-rules` で確認できます。

| ルール | 対象 | 内容 |
| --- | --- | --- |
| `attendee_table` | minutes | 「出席者」節の氏名をバッジ化 |
| `todo_checklist` | minutes | 「ToDo」節をチェックボックス化、`担当: X` / `@X` をバッジ化 |
| `decision_highlight` | minutes | 「決定事項」節をコールアウトで強調 |
| `step_numbering` | procedure | 手順見出しをカード化し自動採番、完了チェック欄を追加 |
| `command_block_copy` | procedure | コードブロックにコピーボタンを追加 |
| `rollback_callout` | procedure | 「切戻し手順」節を警告コールアウト化 |
| `severity_badge` | incident | 重要度をバッジ化（front matter と表の両方） |
| `impact_summary` | incident | 冒頭サマリカードを front matter から組み立て |
| `timeline_table` | incident | 時刻列を持つ表をタイムライン表示に変換 |
| `figure_caption` | spec | 画像を `<figure>` 化し「図 N」を自動採番 |
| `table_caption` | spec | 表に「表 N」のキャプションを付与 |
| `cross_reference` | spec | 本文中の「図 N」「表 N」を図表へのリンク化 |
| `status_badge` | weekly | 表の「状態」列をバッジ化 |
| `progress_bar` | weekly | 表の「進捗」列の `80%` を進捗バー化 |

ルールは **どの種類からでも使えます**。`rules:` に並べた順に適用されるため、
`cross_reference` は採番ルール（`figure_caption` / `table_caption`）より後に置いてください。

---

## front matter のキー

| キー | 説明 |
| --- | --- |
| `type` | 種類。省略すると `default` |
| `title` | 文書タイトル。省略時は最初の見出し → ファイル名の順で決まる |
| その他 | `meta_header` に並べたキーが冒頭のメタ表に出る（`出席者: [山田, 佐藤]` のようなリストも可） |

`incident` では `発生日時` / `復旧日時` / `影響範囲` / `重要度` がサマリカードになります。
`_` で始まるキーはツールの内部用に予約されています。

---

## Exit code

| コード | 意味 |
| --- | --- |
| `0` | 全件成功（警告のみの場合も含む） |
| `1` | 1 件以上の変換に失敗、または対象が見つからない。`--strict` 時は警告があった場合も |
| `2` | 設定エラー / 引数エラー |
| `130` | 中断（Ctrl-C） |

---

## 既知の制約

- **ルールの検出は見出し文字列と表のヘッダ名に依存** します。「出席者」「ToDo」「時刻」「状態」「進捗」など、
  想定の語を含まない見出し / 列名は対象になりません（表記ゆれは `rules/common.py` の定数に追記して対応）。
- **Mermaid は同梱が必要** です。`mermaid: true` にしても `assets/mermaid.min.js` が無ければ警告のうえ図は描画されません
  （CDN は使えない前提のため、自動取得はしません）。
- **画像は 8 MB まで** 埋め込みます。それを超えるものは警告のうえスキップします（base64 でファイルが肥大するため）。
- **手順書のチェック欄は保存されません**。ブラウザ上の作業用です。記録には印刷 / PDF 保存を使ってください。
- 文字コードは **UTF-8 → CP932** の順で読み込みます。それ以外は変換エラーになります。

---

## ファイル構成

```
docmold/
├── docmold.py            エントリポイント（CLI）
├── menu.py               対話メニュー
├── deps.py               依存の確認と案内（サードパーティを import しない）
├── menu.bat              メニューの起動用（Windows でダブルクリック）
├── cli.py                引数解釈・入出力の解決・索引生成
├── config.py             プロファイル定義の読み込みと検証
├── converter.py          変換パイプライン（種類の決定 → Markdown → ルール → 描画）
├── frontmatter.py        front matter の分離
├── renderer.py           Jinja2 描画 / テーマ CSS の組み立て
├── assets.py             画像 base64 埋め込み・同梱資材の読み込み
├── rules/                ② ルール層（意味づけ）
│   ├── __init__.py       レジストリ（@rule デコレータ）
│   ├── common.py         DOM 操作のヘルパ
│   ├── minutes.py  incident.py  procedure.py  spec.py  weekly.py
├── templates/            ① テンプレート層（構造）
│   ├── base.html         共通の骨格
│   ├── article.html  stepped.html  report.html  document.html  dashboard.html
│   └── index.html        一括変換の索引
├── themes/               ③ テーマ層（見た目）
│   ├── base.css          共通スタイル（色は CSS 変数経由）
│   ├── corporate.css  alert.css
│   └── print.css         @media print
├── assets/               同梱資材（mermaid.min.js を置く場所）
├── profiles.yaml         同梱の既定プロファイル定義
├── config.example.yaml   ユーザ設定のテンプレート
├── examples/             種類ごとのサンプル
│   ├── *.md              入力
│   └── html/             変換結果（生成物だが管理対象。tools/build_examples.py が生成）
├── tools/
│   └── build_examples.py examples/html/ の再生成
└── tests/
```

---

## 設計方針

### 3 層に分けて「表現」を差し替える

種類ごとの表現を一枚岩のテンプレートで実現すると、種類が増えるたびにコピペが増えます。
**構造 / 意味づけ / 見た目** を分離し、掛け算で組み合わせられる構成にしています。

| 層 | 役割 | 実体 |
| --- | --- | --- |
| ① テンプレート（構造） | ページの骨格。表紙・目次・ヘッダ / フッタの有無 | `templates/*.html`（Jinja2） |
| ② ルール（意味づけ） | 内容を解釈した変換。「表の"状態"列をバッジにする」 | `rules/*.py`（関数レジストリ） |
| ③ テーマ（見た目） | 色・字送り・印刷設定 | `themes/*.css`（CSS 変数を上書き） |

**プロファイル** = この 3 つの組み合わせ + 設定、と定義しています。
議事録用と障害報告用でテンプレートは同じでもテーマとルールだけ違う、といった再利用ができます。

```
Markdown
   ↓ front matter 分離
   ↓ type からプロファイル決定（未指定なら default）
   ↓ Markdown → HTML 変換（拡張はプロファイル依存）
   ↓ ② ルール層：DOM 後処理
   ↓ ① テンプレート描画 + ③ テーマ CSS 埋め込み
自己完結 HTML（1 ファイル）
```

### 閉域環境を意識した判断

- **完全自己完結 HTML** — 閉域ネットワークでは CDN に出られないため、外部参照ゼロを前提とする。
  ファイルサーバに置いても、メール添付でもそのまま開ける
- **依存は Anaconda 同梱パッケージのみ** — 追加インストールなしで配布先でも動く
- **コピーボタンは `execCommand` にフォールバック** — `file://` や TLS 無しの HTTP では
  `navigator.clipboard` が使えないため
- **印刷（PDF 化）前提の `@media print`** — 記録として PDF 保存する運用に効く

---

## テスト

```bash
pip install -r requirements-dev.txt
python -m pytest
```

`tests/` は層ごとに分かれています（`test_config` / `test_frontmatter` / `test_converter` /
`test_rules` / `test_renderer` / `test_cli` / `test_menu` / `test_examples`）。
ルールを足したら `test_rules.py` に「入力 HTML → 期待する DOM」の形でケースを追加してください。

### サンプル HTML の再生成

`examples/html/` には `examples/*.md` の変換結果を置き、**生成物もリポジトリで管理**しています。
変換処理を変えたときに、見た目の差分をレビューできるようにするためです。

```bash
python tools/build_examples.py            # 再生成する
python tools/build_examples.py --check    # 最新かどうか確認するだけ（古ければ終了コード 1）
```

処理を変えて生成物が古くなると `tests/test_examples.py` が落ちます。
再生成して、**差分を確認したうえで** ソースと一緒にコミットしてください。

```
$ python -m pytest
FAILED tests/test_examples.py::TestGeneratedSamples::test_samples_are_up_to_date
  サンプル HTML が古くなっています: 議事録.html（内容が古い）, …
  python3 tools/build_examples.py で再生成してコミットしてください。
```

- 生成物の先頭には「手で編集しないでください」の注記が入ります
- 内容が変わらないファイルは書き換えません（無駄な差分を作らないため）
- `.md` を消した場合、対応する HTML も削除されます
- **索引 HTML は管理対象外**です。生成時刻を含むため、実行のたびに差分が出てしまいます

---

## 変更履歴

[CHANGELOG.md](CHANGELOG.md) を参照。バージョン番号は付けていません。
