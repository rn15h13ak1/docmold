# docmold

共通規約: [../ws-conventions/README.md](../ws-conventions/README.md) に従う（`~/ws` 配下の全リポジトリ共通）。

各リポジトリ固有の事情は本ファイルに追記する。

## 共通規約からの逸脱

### コミットと push は確認を取らずに行う

共通規約 A は「commit / push は、利用者が明示的に指示したときだけ実行する」としているが、
**本リポジトリでは修正のたびに自動でコミットし、`origin main` へ push する**（2026-09-20 指示）。

- ブランチは切らず `main` に直接コミットする
- 変更 → テスト → CHANGELOG 追記 → コミット → push の順で行う
- 報告には CHANGELOG を更新したことと push 先を書く

日々の小さな修正が多く、そのつど確認を取ると手数が増えるため。

### check-privacy.sh の LICENSE の指摘は許容する

`check-privacy.sh` は `LICENSE:3` の著作権名義を「ユーザー名」として報告するが、
**これは誤検知として許容し、指摘が出たままコミットする**。

意図して書く公開情報であり、作業環境の漏れではない。ライセンス本文は逐語で置くもので、
除外指定の印（`check-privacy:ignore`）も書き足せない。

検査の側を直す提案を `../proposals/ws-conventions-license-copyright.md` に置いた。
反映されたらこの記述は削除する。**LICENSE 以外の指摘は従来どおり 0 件にしてから
コミットする。**
