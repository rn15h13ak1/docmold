# Changelog

[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) 形式に概ね準拠。
バージョン番号は付けていません。

## [Unreleased]

### Added
- front matter の `type` によるプロファイル切り替え（明示指定のみ。パス名や本文からの
  自動判定は行わない。未知の `type` は警告のうえ `default` で処理）
- 3 層分離（テンプレート / ルール / テーマ）と YAML 駆動のプロファイル定義
  - 同梱プロファイル: `default` / `minutes` / `procedure` / `incident` / `spec` /
    `weekly` / `columns`
  - 同梱 `profiles.yaml` にユーザ `config.yaml` を再帰マージ（差分だけ書けばよい）
- ルールの検出語（「出席者」「ToDo」「時刻」「状態」など 13 グループ）を `config.yaml` の
  `keywords:` で差し替え可能。表記ゆれへの対応でコードを直さずに済む
- ルール層のレジストリ（`@rule` デコレータ）。種類の追加は「YAML 数行 + 関数 1 つ」
  - 議事録: `attendee_table` / `todo_checklist` / `decision_highlight`
  - 手順書: `step_numbering` / `command_block_copy` / `rollback_callout`
  - 障害報告: `severity_badge` / `impact_summary` / `timeline_table`
  - 設計書: `figure_caption` / `table_caption` / `cross_reference`
  - 週次報告: `status_badge` / `progress_bar`
  - 列並べ: `count_summary` / `entry_card`
- 完全自己完結 HTML の出力（CSS / JS / 画像 base64 を埋め込み、外部参照ゼロ）
- 本文の生 HTML を許可リストで絞る（既定 `sanitize: strict`）。`script` / `onerror` /
  `javascript:` などを落とし、`<br>` や表の桁揃えは残す。トップレベルの `sanitize` が
  全体の既定、`profiles.<type>.sanitize` が種類ごとの上書き
- 文書間リンク（`[設計書](設計書.md)`）を `.html` に向け直す。フラグメントとクエリは温存し、
  外部 URL とページ内アンカーは書き換えない
- Mermaid の図に対応。```mermaid のコードブロックを描画対象の要素に変換する。
  `figure_caption` は画像だけでなく Mermaid の図も採番し、直前の「図: 説明」を
  キャプションにする。同梱の `spec` は `mermaid: cdn` を使い、サンプル
  `examples/設計書.md` に図を 2 つ入れてある（この出力だけ外部参照を持つ）。
  mermaid.js は CDN 参照（`mermaid: cdn`）と同梱の埋め込み（`mermaid: true`）から選べる。
  既定は無効。CDN 参照にすると、その種類の HTML は自己完結ではなくなる
- 節を横に並べる種類 `columns`。トップレベルの節がそのまま列になり
  （3 つ書けば 3 列）、画面が狭ければ折り返す。列が狭いぶん、表ではなく
  「1 行 1 件」で書けるようルールを 2 つ用意した。
  `count_summary` は `残:3 / 新規:1` だけの段落を件数の並びに、
  `entry_card` は `見出し｜属性｜説明` のリスト項目をカードにする。
  サンプルは `examples/課題サマリー.md`
- 状態バッジの検出語に「再オープン」「期限超過」「期限切れ」を追加
- 印刷用 `@media print`（手順書は見出しごとに改ページ、設計書は表紙を 1 ページ目に、
  障害報告は DRAFT 透かし）。ページ番号を下端に入れる（表紙には出さない）
- ディレクトリ再帰の一括変換と索引 HTML の生成（`--index`）。索引は front matter の
  日付の新しい順に並び、日付を持たないものは最後にまとめる
- `--reproducible` で生成時刻を埋め込まない（索引を差分管理したいとき）

### Fixed
- front matter に `title` が無い場合、見出しに差し込んだ章番号や手順番号が
  タイトルに混ざっていた（`spec` で「1概要」など）
- 別ディレクトリの同名ファイルは出力先をずらして両方残す（`doc.html` / `doc-b.html`）。
  以前は黙って上書きされ、片方の結果が消えていた
- `--list-types` / `--list-rules`、`--type` による上書き、`--dry-run`
- front matter のキーの打ち間違いを警告する（`titel` → `title`）。自由に書いた項目は
  指摘せず、意味を持つキーによく似たものだけを対象にする
- 入力が複数のときに `-o` へ `.html` を渡すと警告する（その名前のディレクトリが
  できることが分かりにくいため）
- `--strict` で警告を失敗扱いにする（終了コード 1）。バッチや定期実行で、
  type のタイプミスや画像の欠落を取りこぼさないため
- 対話メニュー（`menu.py` / `menu.bat`）
- 依存が足りない Python で起動された場合、トレースバックではなく実行中の
  インタプリタと導入コマンドを案内して終了する（`deps.py`）
- サンプル HTML（`examples/html/`）をリポジトリで管理。`tools/build_examples.py` で再生成し、
  古くなると `tests/test_examples.py` が落ちて再生成を促す
- 既定の出力先は docmold 同梱の `out/<YYYYMMDD-HHMMSS>/`
  （起動位置に依存せず、実行ごとにフォルダを分離）。`-o` を指定した場合は
  そのパスをそのまま使う
- 出力フォルダは排他的に作成する。同じ秒に複数のプロセスが走っても、
  フォルダを共有して出力が混ざることがない（連番が付く）
