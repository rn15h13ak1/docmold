# assets/

自己完結 HTML に埋め込む同梱資材の置き場。

**図（Mermaid）を CDN から読み込む場合は、ここに何も置く必要はありません。**
`profiles.<種類>.mermaid: cdn` を設定してください（詳しくは README の「図を使う」）。

## mermaid.min.js

プロファイルで `mermaid: true`（＝ `bundled`）を指定した場合だけ、ここの
`mermaid.min.js` が HTML に埋め込まれます。外部参照を持たせたくない
（閉域ネットワークで図を出したい）場合の選択肢です。

ファイルが無い場合は警告を出したうえで、図なしで変換を続けます（自動ダウンロードはしません）。

配置するには、外部に出られる端末で以下を取得し、このディレクトリに `mermaid.min.js`
として置いてください。

    https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js

> **サイズに注意。** このファイルは約 3.4 MB あり、図を使う HTML 1 ファイルごとに
> まるごと埋め込まれます。メール添付で配る場合は CDN 参照のほうが現実的です。

## 図の書き方

Markdown 側は、`mermaid` を指定したコードブロックとして書きます。

    ```mermaid
    graph TD
      A[受付] --> B[審査]
    ```

`mermaid` が無効なプロファイルでは、ただのコードブロックとして表示されます。
