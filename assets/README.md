# assets/

自己完結 HTML に埋め込む同梱資材の置き場。閉域ネットワークでは CDN に出られないため、
外部から取得するのではなくここに置いたものを読み込みます。

## mermaid.min.js

プロファイルで `mermaid: true` を指定すると、ここの `mermaid.min.js` が HTML に埋め込まれます。

ファイルが無い場合は警告を出したうえで、図なしで変換を続けます（自動ダウンロードはしません）。

配置するには、外部に出られる端末で以下を取得し、このディレクトリに `mermaid.min.js` として置いてください。

    https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js

Markdown 側では、`mermaid` クラスを付けたコードブロックとして書きます。

    ``` { .mermaid }
    graph TD
      A[受付] --> B[審査]
    ```
