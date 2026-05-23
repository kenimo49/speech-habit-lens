# AmiVoice API Key 取得ガイド

> **対象:** speech-habit-lens を初めて動かす人
> **所要時間:** 約10分
> **費用:** 無料（月60分の無料枠内で運用する想定）

このガイドは [AmiVoice Cloud Platform](https://acp.amivoice.com/main/) のアカウント登録から、API キーを取得して `.env` に設定し、`curl` で疎通確認するまでを通しで案内します。

---

## 1. 前提

| 必要なもの | 用途 |
|---|---|
| メールアドレス | アカウント登録・認証メール受信用 |
| クレジットカード（任意） | 無料枠（月60分）を超えて使う場合のみ必要。最初は登録不要 |

**無料枠について（重要）**

- **全エンジン共通で月60分まで無料**（エンジンごとに60分ずつ加算ではなく、合計60分）
- ESAS（感情分析）も無料枠の対象
- 超過すると `¥79.2/時間〜` の従量課金
- speech-habit-lens は1解析≒1分なので、**月60本まで実質無料**で運用できる

### Zennfes 2026 春 — Trial クーポン（2026年5月・6月限定）

Zennfes 2026 春のスポンサー枠（株式会社アドバンスト・メディア）で、**月10時間（600分）無償**の Trial クーポンが配布されている。speech-habit-lens の開発期間（2026-05〜06）はこちらを使えば、無料枠を気にせず実装と検証が可能。

- クーポンコード: `Na5bkyRHoi`
- 適用先: AmiVoice API（ESAS 含む）
- 期間: 2026年5月・6月
- 適用方法: アカウント登録後、マイページの `TBD: クーポン入力画面の場所` でコードを入力

> Zennfes 期間後（2026年7月以降）は通常の月60分無料枠に戻る。本ツールの設計（1解析≒1分）であれば通常運用も無料枠で収まる。
> このクーポンは Zennfes 参加者向けに公開されたコードのため、本リポジトリにも記載している。Zennfes 期間外に始める読者は AmiVoice 公式から通常登録すれば月60分の無料枠で動かせる。

---

## 2. ステップ 1 — アカウント登録

1. [https://acp.amivoice.com/main/](https://acp.amivoice.com/main/) にアクセス
2. 画面右上の `TBD: 新規登録ボタンの名称` をクリック
3. `TBD: 登録フォームの項目` を入力
   - メールアドレス
   - パスワード
   - 氏名 / 会社名（任意 or 必須かを実画面で確認）
4. 利用規約に同意
5. 登録完了ボタンを押す

### 認証メール

- 登録後、`TBD: 送信元メールアドレス` から認証メールが届く
- メール内のリンクをクリックして本登録を完了
- リンク有効期限: `TBD`

> **トラブル:** メールが届かない場合は迷惑メールフォルダを確認。それでも届かない場合は `TBD: 問い合わせ先`。

---

## 3. ステップ 2 — マイページにログイン

1. [https://acp.amivoice.com/main/](https://acp.amivoice.com/main/) からログイン
2. ダッシュボード（My Page）が開く
3. `TBD: 左サイドバー or 上部ナビゲーション` から「API キー管理」「アプリケーションキー」相当のメニューに移動

### マイページの主な機能（参考）

- API キー（APPKEY）の発行・再発行
- 利用量モニタリング（月別の認識時間）
- ESAS など追加機能のオプション設定
- 請求情報・支払い方法

---

## 4. ステップ 3 — API キーを発行

1. `TBD: API キー発行画面のメニュー名` を開く
2. `TBD: 発行ボタン` をクリック
3. 表示されたキー（APPKEY）をコピー
   - 形式: `TBD: キーの形式（例: 32文字英数字 / UUID / Base64 等）`
   - **このキーは秘密情報。第三者に公開しない、Git にコミットしない**

### One-time APPKEY について

ACP では使い捨て用の APPKEY も発行できる（`Issuance of one-time APPKEY`）。
本ツールは常時稼働ではないので、**通常の APPKEY で十分**。

### ESAS の有効化

ESAS は標準で有効か、別途オプション ON が必要か `TBD: 実画面で確認`。
- もしオプション ON が必要なら、ここで `Sentiment Analysis` 相当の機能を有効化する
- 月60分の無料枠は ESAS にも適用される

---

## 4.5 ステップ 3.5 — Zennfes Trial クーポンを適用（2026年5・6月のみ）

> このセクションは Zennfes 2026 春の参加者向け。通常運用なら飛ばして良い。

1. マイページの `TBD: クーポン入力画面の場所` を開く
2. クーポンコード `Na5bkyRHoi` を入力
3. 適用ボタンを押す
4. 利用枠が「月10時間（600分）」に拡大されたことを確認

`TBD: クーポン適用後のダッシュボード表示` で残り利用時間を確認できる。

---

## 5. ステップ 4 — `.env` に書く

リポジトリのルートで `.env.example` をコピーして `.env` を作成:

```bash
cd /path/to/speech-habit-lens
cp .env.example .env
```

エディタで `.env` を開いて、取得した APPKEY を書き込む:

```bash
AMIVOICE_API_KEY=ここに取得したAPPKEYを貼る
ANTHROPIC_API_KEY=後で設定（Claude 用、別途必要）
```

> **注意:** `.env` は `.gitignore` 済み。誤って `git add` しないこと。

---

## 6. ステップ 5 — `curl` で疎通確認

API キーが正しく機能するかを、サンプル音声を投げて確認する。

### 6.1 サンプル音声を用意

手元に短い `.wav`（10〜30秒、16kHz/16bit/mono 推奨）がなければ、`examples/sample.wav` を使う（ない場合は後述のコマンドで生成）。

### 6.2 ジョブを submit

```bash
source .env
curl -X POST https://acp-api-async.amivoice.com/v1/recognitions \
  -F "u=$AMIVOICE_API_KEY" \
  -F "d=grammarFileNames=-a-general sentimentAnalysis=True" \
  -F "a=@examples/sample.wav"
```

レスポンス例:

```json
{"sessionid": "01234567-89ab-cdef-0123-456789abcdef", "text": null}
```

`sessionid` をメモする。

### 6.3 結果を取得

数秒待ってから:

```bash
curl https://acp-api-async.amivoice.com/v1/recognitions/$SESSION_ID \
  -H "Authorization: Bearer $AMIVOICE_API_KEY"
```

`status` が `completed` になったレスポンスに、認識テキストと ESAS 結果が入っている。

### 6.4 動作確認できたら

- 認識テキストが返れば API キーは有効
- `sentiment_analysis` フィールドに 20 パラメータの時系列が入っていれば ESAS も有効

---

## 7. トラブルシュート

| 現象 | 原因 | 対処 |
|---|---|---|
| `code: "-"` が返る | APPKEY が無効 | マイページで APPKEY を再確認、`.env` のスペース混入チェック |
| `code: "+"` が返る | 音声フォーマット非対応 | WAV の PCM 16bit/mono/16kHz に変換 |
| 401 Unauthorized | GET の Bearer ヘッダが間違い | `Authorization: Bearer ` の後にキーをそのまま貼る（プレフィックス不要） |
| ESAS フィールドが空 | `sentimentAnalysis=True` が抜けている、または音量が極端に小さい | `d` パラメータを確認、音声の音量チェック |
| 月60分超過の通知 | 無料枠超過 | マイページで利用量確認、必要なら課金設定 |

---

## 8. 利用量のモニタリング

- マイページの `TBD: 利用量ダッシュボードの場所` で月別の認識時間を確認できる
- speech-habit-lens 自体には利用量カウント機能はない（v0.2 で検討）
- 月の上限が近づいたら手動で運用を絞る

---

## 9. 関連リンク

- [AmiVoice Cloud Platform](https://acp.amivoice.com/main/) — 公式トップ
- [API マニュアル](https://docs.amivoice.com/) — 完全リファレンス
- [ESAS サービス](https://acp.amivoice.com/main/service/esas/) — 感情分析の解説
- [料金ページ](https://acp.amivoice.com/main/charge/) — 課金体系

### 本リポジトリの関連ドキュメント

- [Overview](../knowledge/amivoice-overview.md) — AmiVoice サービス全体像
- [API Reference](../knowledge/amivoice-api-reference.md) — 3インタフェースの詳細
- [ESAS 20パラメータ](../knowledge/amivoice-esas.md) — 感情分析の完全リファレンス
