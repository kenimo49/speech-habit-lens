# AmiVoice ESAS — 感情分析リファレンス

> 一次ソース:
> - https://docs.amivoice.com/en/amivoice-api/manual/sentiment-analysis/
> - https://docs.amivoice.com/en/amivoice-api/manual/reference-list-sentiment-analysis-parameters/
> - https://acp.amivoice.com/main/service/esas/
>
> Source verified: 2026-05-22

ESAS (Emotion Speech Analysis Service) は AmiVoice の感情分析オプション。本ツール speech-habit-lens の差別化の核となる機能。

## 概要

- **提供元**: ES Japan (Nemesysco 技術ベース)
- **入力**: 音声 (テキストではない、声の音響特徴から判定)
- **出力**: 20 個の感情パラメータ × N 個の時間セグメント
- **サンプリング**: 約 2 秒に1回
- **対応言語 (認識側)**: 日本語 / 英語 / 中国語 / 韓国語
- **対応言語 (パラメータ説明)**: 日本語のみ (`ja`)

## 重要な制約

| 制約 | 影響 |
|---|---|
| **非同期 HTTP v1 のみ対応** | 同期 HTTP / WebSocket / 非同期 v2 では使えない |
| **音声音量の閾値あり** | normalized scale で 0.1 未満の区間は ESAS 出力対象外 |
| **無料枠 月60分** | 超過時は料金が発生 |
| **2秒間隔のサンプリング** | 60秒スピーチで約 30 サンプル |

## 有効化方法

非同期 HTTP v1 のリクエストに `sentimentAnalysis=True` を追加する。

```bash
curl https://acp-api-async.amivoice.com/v1/recognitions \
  -F u=$AMIVOICE_API_KEY \
  -F d='grammarFileNames=-a-general sentimentAnalysis=True keepFillerToken=1' \
  -F a=@speech.wav
```

`d` パラメータ内に空白区切りで `sentimentAnalysis=True` を入れる。

## 20 パラメータ一覧

公式ドキュメント (英語版) から確認できる ESAS の 20 パラメータ。

### 主要 3 パラメータ (公式推奨)

| パラメータ | 範囲 | 内容 |
|---|---|---|
| **Energy** | 0–100 | 感情の興奮度合い・疲労度の基本指標 |
| **Stress** | 0–100 | 精神的負荷。高値は negative outcome を示唆 |
| **Emotional-Balanced-Logical** | 1–500 | 思考様式の分類 (logical / balanced / emotional) |

### その他 17 パラメータ

| パラメータ | 内容 |
|---|---|
| Concentration | 集中度 |
| Anticipation | 期待 |
| Excitement | 興奮 |
| Hesitation | 躊躇 |
| Uncertainty | 不確実性 |
| Thinking | 思考 |
| Imagination | 想像 |
| Confusion | 混乱 |
| Passion | 情熱 |
| Brain Activity | 脳活動 |
| Confidence | 自信 |
| Aggression / Anger | 攻撃性・怒り |
| Atmosphere / Conversation Trend | 雰囲気・会話傾向 |
| Agitation | 動揺 |
| Joy | 喜び |
| Dissatisfaction | 不満 |
| Extreme Fluctuation | 極端な変動 |

> **注**: 各パラメータの正確な値域と詳細定義は API 経由で取得可能 (後述「パラメータ定義の取得 API」参照)。本ツールは初回 API 呼び出し時にこの定義を読み込んで `docs/knowledge/amivoice-esas.md` を更新する運用とする。

## 出力 JSON 構造

ESAS を有効化した非同期 HTTP v1 のレスポンスには `sentiment_analysis` フィールドが含まれる。

```json
{
  "text": "今日はピッチの練習をします...",
  "segments": [...],          // 通常の認識結果
  "sentiment_analysis": {
    "segments": [
      {
        "starttime": 0,
        "endtime": 2000,
        "Energy": 65,
        "Stress": 30,
        "Emotional-Balanced-Logical": 250,
        "Concentration": 70,
        "Anticipation": 55,
        "Excitement": 40,
        "Hesitation": 20,
        "Uncertainty": 15,
        "Thinking": 60,
        "Imagination": 35,
        "Confusion": 10,
        "Passion": 45,
        "Brain Activity": 75,
        "Confidence": 60,
        "Aggression": 5,
        "Atmosphere": 50,
        "Agitation": 25,
        "Joy": 40,
        "Dissatisfaction": 15,
        "Extreme Fluctuation": 20
      },
      {
        "starttime": 2000,
        "endtime": 4000,
        ...
      }
    ]
  }
}
```

**フィールド名は実装時に実 API レスポンスで再確認すること** (`Aggression Anger` vs `Aggression-Anger` 等の表記揺れの可能性)。

## パラメータ定義の取得 API

ESAS パラメータの公式定義 (display name, min/max) を JSON で取得できる。

### Endpoint

```
GET https://acp-dsrpp.amivoice.com/v1/sentiment-analysis/{language}/result-parameters.json
```

- `{language}`: 現状 `ja` のみサポート

### 認証

```
Authorization: Bearer {APPKEY}
```

### レスポンス構造

```json
{
  "sentiment_analysis": {
    "result_parameters": {
      "display_language": "ja",
      "definitions": [
        {
          "name": "Energy",
          "display_name": "活力",
          "minimum": 0,
          "maximum": 100
        },
        {
          "name": "Stress",
          "display_name": "ストレス",
          "minimum": 0,
          "maximum": 100
        }
      ]
    }
  }
}
```

### speech-habit-lens での活用

`shl init-esas-meta` (仮) で実 API を叩き、`docs/knowledge/amivoice-esas.md` の表を最新化する運用を検討。

## speech-habit-lens 設計への影響

### なぜ async HTTP v1 を選んだか

ESAS が **v1 のみ対応**だから。v2 のリリースが新しいが、ESAS という核機能のために v1 を採用する。将来 v2 で ESAS が対応されたら移行する。

### 主要 3 パラメータの使い方

| パラメータ | 1分スピーチでの解釈 |
|---|---|
| **Energy** | 「出だしのテンション」「中盤の失速」を検出 |
| **Stress** | 「結論手前の不安」「想定外質問への動揺」を検出 |
| **Emotional-Balanced-Logical** | 「ロジック先行」「感情先行」のスタイル指標 |

### 二次パラメータの活用候補

| 用途 | パラメータ |
|---|---|
| 自信のなさ検出 | Hesitation, Uncertainty, Confidence |
| ノリの良さ | Joy, Excitement, Passion |
| 知的緊張 | Concentration, Thinking, Brain Activity |
| ネガティブ反応 | Dissatisfaction, Aggression, Agitation |

### LLM へ渡すデータ量

60秒スピーチで約30サンプル × 20パラメータ = 600 数値。JSON で 3-4KB 程度。Claude のコンテキストには余裕で収まる。

### ノイズと欠落

- 無音 / 極小音量区間は ESAS セグメントが出ない
- 60秒中に欠落セグメントがあれば、テキスト層の対応セグメントも欠ける可能性
- レポートでは「ESAS 取得 N/30 サンプル」のように明示する

## 制約と倫理

- ESAS は音声の音響特徴からの推定であり、本人の主観的感情と完全一致するわけではない
- 採用面接や評価に直接使うのは倫理的に慎重に。本ツールは**自己レビュー用**を主目的とする
- 第三者の音声を解析する場合は事前同意が必要

## 関連リンク

- ESAS マニュアル (EN): https://docs.amivoice.com/en/amivoice-api/manual/sentiment-analysis/
- パラメータ取得 API: https://docs.amivoice.com/en/amivoice-api/manual/reference-list-sentiment-analysis-parameters/
- ESAS サービスページ: https://acp.amivoice.com/main/service/esas/
- ES Japan 公式: https://www.es-jpn.jp/
- 提供元 Nemesysco: https://nemesysco.com/
- 非同期 HTTP リファレンス: https://docs.amivoice.com/amivoice-api/manual/reference-async-http/
- リリースブログ (2022-07): https://acp.amivoice.com/en/blog/2022-07-04-150000/
