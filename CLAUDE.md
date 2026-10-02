# docmold

共通規約: [../ws-conventions/README.md](../ws-conventions/README.md) に従う（`~/ws` 配下の全リポジトリ共通）。

各リポジトリ固有の事情は本ファイルに追記する。

## 検査

編集したら、コミット前に次を実行する。

```bash
../ws-conventions/bin/check-markdown.sh .
../ws-conventions/bin/check-privacy.sh .
python tools/build_examples.py
```

`tools/build_examples.py` は `examples/html/` を再生成し、**生成物に変換した端末の絶対パスが
混ざっていれば終了コード 1 で止める**（[規約 B](../ws-conventions/README.md#b-個人情報の扱い)
が求める生成物の検査）。変換処理を変えたら必ず通す。`pytest` も生成物が古いと落ちる。

**ADR は使っていない。** 種類の追加は YAML とルール関数で閉じており、意思決定の記録を残すほどの
選択が本リポジトリに無いため。したがって `check-terms.sh` と `gen-decision-index.py` は対象外。

`bin/` にも `scripts/` にも検査スクリプトを置いていないため、`check-commands.sh` も対象外。
`tools/` にあるのは生成物のビルドで、検査スクリプトではない。

## commit / push

[規約 A](../ws-conventions/README.md#commit--push-の判断) のとおり、検査とテストが通ったら指示を待たずに
コミットして `origin main` へ push する。修正のたびに行い、確認は取らない。
2026-09-20 の指示から逸脱として記録していたが、2026-10-02 の規約 A の改定で規約どおりになった。

- ブランチは切らず `main` に直接コミットする
- 変更 → テスト → [検査](#検査) → CHANGELOG 追記 → **プレフィックスを選ぶ** → コミット → push の順で行う
- 報告には CHANGELOG を更新したことと push 先を書く

**確認を取らないぶん、規約 A のプレフィックス（`feat:` `fix:` `docs:` など）を飛ばしやすい。**
2026-09-18 の規約制定後、本リポジトリのコミット 15 件のうち 12 件で付け忘れていた。
自動でコミットする以上、ここは手順の中に置いて毎回選ぶ。
