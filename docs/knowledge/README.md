# Knowledge Base

speech-habit-lens 開発に必要な外部サービス・API・ドメイン知識のリファレンス。
公式ドキュメントの抜粋を整理し、本リポジトリの設計判断と紐付ける。

## ドキュメント一覧

| ファイル | 内容 | 一次ソース |
|---|---|---|
| [amivoice-overview.md](amivoice-overview.md) | AmiVoice の全体像、エンジン種類、価格、無料枠 | [公式サイト](https://acp.amivoice.com/main/) |
| [amivoice-api-reference.md](amivoice-api-reference.md) | API リファレンス: 3インタフェース、エンドポイント、パラメータ、レスポンス JSON | [API マニュアル](https://docs.amivoice.com/) |
| [amivoice-esas.md](amivoice-esas.md) | **ESAS (感情分析) 完全リファレンス**: 20パラメータ全リスト、有効化、出力JSON | [Sentiment Analysis](https://docs.amivoice.com/en/amivoice-api/manual/sentiment-analysis/) |

## このリポジトリで採用した実装パターン

| 採用 | 理由 |
|---|---|
| **Async HTTP v1** | ESAS は v1 でのみ利用可能 (v2は未対応)。本ツールの差別化の核がESASなのでv1一択 |
| **`-a-general` エンジン** | end-to-end 汎用エンジン、最新かつ ATS で自動学習継続 |
| **`keepFillerToken=1`** | 癖分析のためフィラーを保持 (デフォルトは削除されてしまう) |
| **`sentimentAnalysis=True`** | ESAS 有効化フラグ |
| **`speakerDiarization=False`** | 1人スピーチ前提なので不要 |
| **CLI + Streamlit ローカル UI 同梱** | OSS 再現性 (`git clone` で動く) と見栄え (ブラウザ + Plotlyチャート) を両取り、API key 漏洩リスクなし |

詳細な設計判断は [Issue #1](https://github.com/kenimo49/speech-habit-lens/issues/1) と [docs/design.md](../design.md) を参照。

## 更新ポリシー

- 公式ドキュメント側に変更が入った場合は、ファイル末尾の "Source verified" 日付を更新する
- 公式仕様と実装が乖離した場合、実装の根拠コメントから本ファイルへリンクする
- 不確実な情報は推測せず「要API確認」と明記する
