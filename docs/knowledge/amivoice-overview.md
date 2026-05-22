# AmiVoice Cloud Platform — Overview

> 一次ソース: https://acp.amivoice.com/main/
> Source verified: 2026-05-22

## 概要

AmiVoice Cloud Platform (ACP) は株式会社アドバンスト・メディア (Advanced Media) が提供するクラウド型音声認識 API サービス。日本の音声認識市場で長年のシェアを持つ。

**提供サービス:**
- AmiVoice API (本リポジトリで利用するクラウド API)
- AmiVoice API Private (専有環境)
- AmiVoice SDK (オンプレ/エッジ用)

## エンジン種類

AmiVoice はエンジンを2系統で分類している。

### End-to-End エンジン (推奨)

最新方式。汎用エンジンが主軸。

| 識別子 | 用途 | 特徴 |
|---|---|---|
| `-a-general` | 汎用 (会話) | 自動学習システム (ATS) で新語彙に継続対応 |

### Hybrid エンジン (専門領域)

業界別の特化モデル。専門用語の認識精度が高い。

| 領域 | 用途 |
|---|---|
| Medical | 医療用語 |
| Insurance | 保険業務 |
| Finance | 金融業務 |
| Name | 人名認識 |
| Address | 住所認識 |

### 音響モデル

エンジンとは別軸で2種類:
- **会話 (Conversation)** — 自然な会話音声
- **音声入力 (Voice input)** — フォーム入力等の単発発話

### 対応言語

日本語 / 英語 / 中国語 / 韓国語 / 多言語

## インタフェース

3種類の API インタフェースを提供。詳細は [amivoice-api-reference.md](amivoice-api-reference.md)。

| インタフェース | 用途 | speech-habit-lens での利用 |
|---|---|---|
| 同期 HTTP | 短い音声 (~1分) を一発で送信 | ❌ ESAS 非対応のため不採用 |
| 非同期 HTTP | 長い音声 + バッチ処理 | ✅ **本ツールが採用** |
| WebSocket | リアルタイムストリーミング | ❌ MVP では不要 |

## 価格

> 一次ソース: https://acp.amivoice.com/main/charge/

### 基本料金

- **¥79.2/時間〜** (従量課金、初期費用なし)
- エンジンごとに単価が異なる (medical/finance 等の専門エンジンは高め)

### 無料枠

- **全エンジン 月60分無料** (エンジンごとに 60 分ずつ計算)
- **ESAS も月60分無料**

speech-habit-lens は1解析あたり1分以下を強制するので、無料枠で月60本まで実行可能。

### ESAS の費用

ESAS は別オプション扱いだが、月60分の無料枠あり。超過分のレート詳細は公式料金ページ参照。

## ESAS (感情分析)

AmiVoice の差別化機能のひとつ。詳細は [amivoice-esas.md](amivoice-esas.md)。

- ES Japan が提供する Nemesysco 技術ベース
- 音声から感情を 20 パラメータで抽出
- 約2秒間隔でサンプリング
- **非同期 HTTP v1 でのみ利用可能** (v2 では未対応)

## 認証

API キーは ACP ダッシュボード (My Page) で発行。

- 同期 HTTP / 非同期 HTTP POST: form parameter `u` で送信
- 非同期 HTTP GET (結果取得): `Authorization: Bearer {APPKEY}` ヘッダ

API キー再生成も `Issuance of one-time APPKEY` で可能 (使い捨て向け)。

## 推奨追加機能

| 機能 | 用途 |
|---|---|
| プロフィール (`profileId`/`profileWords`) | ユーザー辞書、専門用語登録 |
| Speaker Diarization | 話者分離 (事前学習不要、自動識別) |
| Sentiment Analysis (ESAS) | 感情分析 ← 本ツールの核 |
| `keepFillerToken` | フィラー (えーと等) の保持/削除制御 |

## 制限事項

公式ドキュメントから読み取れる主な制約:

- 音声の音量が極端に小さい区間は ESAS 出力対象から除外される (normalized scale で 0.1 未満)
- ESAS は非同期 HTTP v1 のみ
- セッション ID は一定期間で expired (404 返却)、結果取得は早めに

## 関連リンク

- 公式: https://acp.amivoice.com/main/
- API マニュアル: https://docs.amivoice.com/
- 英語マニュアル: https://docs.amivoice.com/en/
- ESAS サービスページ: https://acp.amivoice.com/main/service/esas/
- 提供元 (Advanced Media): https://www.advanced-media.co.jp/
- ESAS 技術提供元 (ES Japan / Nemesysco): https://www.es-jpn.jp/
