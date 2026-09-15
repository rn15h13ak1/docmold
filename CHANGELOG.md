# Changelog

[Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) 形式に概ね準拠。
バージョン番号は付けていません。

## [Unreleased]

### Added
- front matter の `type` によるプロファイル切り替え（明示指定のみ。パス名や本文からの
  自動判定は行わない。未知の `type` は警告のうえ `default` で処理）
- 3 層分離（テンプレート / ルール / テーマ）と YAML 駆動のプロファイル定義
  - 同梱プロファイル: `default` / `minutes` / `procedure` / `incident` / `spec` / `weekly`
  - 同梱 `profiles.yaml` にユーザ `config.yaml` を再帰マージ（差分だけ書けばよい）
- ルール層のレジストリ（`@rule` デコレータ）。種類の追加は「YAML 数行 + 関数 1 つ」
  - 議事録: `attendee_table` / `todo_checklist` / `decision_highlight`
  - 手順書: `step_numbering` / `command_block_copy` / `rollback_callout`
  - 障害報告: `severity_badge` / `impact_summary` / `timeline_table`
  - 設計書: `figure_caption` / `table_caption` / `cross_reference`
  - 週次報告: `status_badge` / `progress_bar`
- 完全自己完結 HTML の出力（CSS / JS / 画像 base64 を埋め込み、外部参照ゼロ）
- 印刷用 `@media print`（手順書は見出しごとに改ページ、設計書は表紙を 1 ページ目に、
  障害報告は DRAFT 透かし）
- ディレクトリ再帰の一括変換と索引 HTML の生成（`--index`）
- `--list-types` / `--list-rules`、`--type` による上書き、`--dry-run`
- 対話メニュー（`menu.py` / `menu.bat`）
- 依存が足りない Python で起動された場合、トレースバックではなく実行中の
  インタプリタと導入コマンドを案内して終了する（`deps.py`）
- サンプル HTML（`examples/html/`）をリポジトリで管理。`tools/build_examples.py` で再生成し、
  古くなると `tests/test_examples.py` が落ちて再生成を促す
- 既定の出力先は docmold 同梱の `out/<YYYYMMDD-HHMMSS>/`
  （起動位置に依存せず、実行ごとにフォルダを分離）。`-o` を指定した場合は
  そのパスをそのまま使う
