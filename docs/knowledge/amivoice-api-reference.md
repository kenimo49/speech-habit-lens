# AmiVoice API Reference

> 一次ソース: https://docs.amivoice.com/
> Source verified: 2026-05-22

AmiVoice Cloud Platform が提供する 3 つの API インタフェースの完全リファレンス。

## インタフェース比較

| インタフェース | エンドポイント | 用途 | ESAS |
|---|---|---|---|
| 同期 HTTP | `https://acp-api.amivoice.com/v1/recognize` | 短い音声 (~1分) を即時取得 | ❌ |
| 非同期 HTTP v1 | `https://acp-api-async.amivoice.com/v1/recognitions` | 長い音声 + バッチ、**ESAS 必須時** | ✅ |
| 非同期 HTTP v2 | `https://acp-api-async.amivoice.com/v2/recognitions` | 同上の最新版 | ❌ (未対応) |
| WebSocket | `wss://acp-api.amivoice.com/v1/` | リアルタイムストリーミング | ❌ |

ログを保存しないバージョンは末尾に `/nolog/` を挿入 (例: `https://acp-api.amivoice.com/v1/nolog/recognize`)。

## 認証

| インタフェース | 方式 |
|---|---|
| 同期 HTTP | form parameter `u={APPKEY}` |
| 非同期 HTTP (POST submit) | form parameter `u={APPKEY}` |
| 非同期 HTTP (GET status/result) | `Authorization: Bearer {APPKEY}` ヘッダ |
| WebSocket | コマンドパケット内に APP KEY を含める |

API キーは ACP マイページから発行。

---

## 1. 同期 HTTP インタフェース

短い音声を一発で投げて即座にテキストを受け取る。本ツールでは ESAS 非対応のため**未採用**だが、参考として記載。

### Endpoint

```
POST https://acp-api.amivoice.com/v1/recognize
POST https://acp-api.amivoice.com/v1/nolog/recognize  # ログ無効化
```

### 必須パラメータ

| 名前 | 用途 |
|---|---|
| `u` | API キー |
| `d` | エンジン設定 (例: `grammarFileNames=-a-general`) |
| `a` | 音声バイナリ (multipart の **最後** に配置) |
| `c` | RAW/PCM 入力時のフォーマット指定 |

### `d` パラメータの中身

`<key>=<value> <key>=<value>` 形式 (スペース区切り)。

| キー | 必須 | 内容 |
|---|---|---|
| `grammarFileNames` | ✅ | エンジン名 (例: `-a-general`) |
| `profileId` | | ユーザー辞書 ID |
| `profileWords` | | セッション固有の語登録 |
| `keepFillerToken` | | フィラー保持 (`1`) / 削除 (`0`、デフォルト) |

### curl サンプル

```bash
curl https://acp-api.amivoice.com/v1/recognize \
  -F u=$AMIVOICE_API_KEY \
  -F d='grammarFileNames=-a-general' \
  -F a=@speech.wav
```

### レスポンス JSON

```json
{
  "results": [{
    "tokens": [
      {"written": "今日", "spoken": "きょう", "confidence": 0.95, "starttime": 522, "endtime": 1578}
    ],
    "confidence": 0.998,
    "starttime": 250,
    "endtime": 8794,
    "text": "今日はいい天気です"
  }],
  "utteranceid": "20220602/14/018122d65d370a30116494c8",
  "text": "今日はいい天気です",
  "code": "",
  "message": ""
}
```

### エラーコード (`code` フィールド、1文字)

| コード | 意味 |
|---|---|
| `+` | 非対応音声フォーマット |
| `-` | API キー不正 |
| `!` | サーバ接続失敗 |
| `o` | confidence が閾値未満 |
| `?` | サーバ致命エラー |
| `""` (空) | 成功 |

---

## 2. 非同期 HTTP インタフェース (本ツール採用)

ジョブを submit して polling で結果取得。ESAS が利用できるのは **v1 のみ**。

### Endpoint

```
POST https://acp-api-async.amivoice.com/v1/recognitions   # submit
GET  https://acp-api-async.amivoice.com/v1/recognitions/{session_id}   # polling/結果取得
```

### Step 1: ジョブ submit

```bash
curl https://acp-api-async.amivoice.com/v1/recognitions \
  -F u=$AMIVOICE_API_KEY \
  -F d='grammarFileNames=-a-general sentimentAnalysis=True keepFillerToken=1' \
  -F a=@speech.wav
```

レスポンス (成功時):
```json
{
  "sessionid": "017ac8786c5b0a0504399999",
  "text": ""
}
```

### Step 2: 状態 polling + 結果取得

```bash
curl -H "Authorization: Bearer $AMIVOICE_API_KEY" \
  https://acp-api-async.amivoice.com/v1/recognitions/017ac8786c5b0a0504399999
```

`status` フィールドの値:

| 値 | 意味 |
|---|---|
| `queued` | 待機中 |
| `started` | 処理開始 |
| `processing` | 処理中 |
| `completed` | 完了 |
| `error` | エラー |

### 非同期固有パラメータ

| パラメータ | 値 | 内容 |
|---|---|---|
| `loggingOptOut` | Bool | ログ保存無効化 |
| `contentId` | 任意 | ユーザー側 ID、レスポンスに含まれる |
| `compatibleWithSync` | Bool | 同期 HTTP 互換フォーマットで返す |
| `speakerDiarization` | Bool | 話者分離有効化 |
| `diarizationMinSpeaker` | Int | 最小話者数 (default 1) |
| `diarizationMaxSpeaker` | Int | 最大話者数 (default 10) |
| `sentimentAnalysis` | Bool | **ESAS 有効化 (v1 のみ)** |

### レスポンス JSON (完了時)

```json
{
  "segments": [
    {
      "results": [{
        "tokens": [
          {"written": "今日", "spoken": "きょう", "starttime": 522, "endtime": 1578, "confidence": 0.95}
        ],
        "text": "今日はいい天気です"
      }],
      "text": "今日はいい天気です"
    }
  ],
  "utteranceid": "...",
  "text": "今日はいい天気です。明日は雨です。",
  "status": "COMPLETED",
  "session_id": "017ac8786c5b0a0504399999",
  "audio_size": 0,
  "code": "",
  "message": "",
  "sentiment_analysis": {
    "segments": [
      {
        "starttime": 0,
        "endtime": 2000,
        "Energy": 65,
        "Stress": 30,
        "Emotional-Balanced-Logical": 250
      }
    ]
  }
}
```

### HTTP エラーコード

| コード | 意味 |
|---|---|
| 401 | 認証失敗 (header 欠落 or API キー不正) |
| 404 | セッション ID 不在 (expired or 他ユーザのもの) |
| 500 | サーバ内部エラー |

---

## 3. WebSocket インタフェース

本ツールでは未使用だが、v1.0 のリアルタイム解析機能で採用候補。

### Endpoint

```
wss://acp-api.amivoice.com/v1/
wss://acp-api.amivoice.com/v1/nolog/
```

クライアント・サーバ間でコマンドパケット (`s`/`p`/`e`)、レスポンスパケット、イベントパケットを送受信する双方向プロトコル。詳細は [WebSocket 公式リファレンス](https://docs.amivoice.com/amivoice-api/manual/reference-websocket/) を参照。

---

## 共通パラメータ (全インタフェース)

| パラメータ | 内容 |
|---|---|
| `grammarFileNames` | **必須**、エンジン名 |
| `profileId` | ユーザー辞書 ID |
| `profileWords` | 語登録 (`|` 区切りで複数指定可) |
| `keepFillerToken` | フィラー保持 (`0`/`1`) |
| `segmenterProperties` | 発話区間検出のチューニング (`threshold`/`preTime`/`postTime` etc.) |
| `extension` | 集計用タグ |
| `maxDecodingTime` | 処理時間上限 (ms) |
| `maxResponseTime` | 応答時間上限 (ms) |
| `recognitionTimeout` | 認識タイムアウト (ms) |

## レスポンス共通フィールド

| フィールド | 内容 |
|---|---|
| `utteranceid` | 結果情報 ID |
| `text` | 全文認識結果 |
| `code` | 1文字エラーコード (空文字=成功) |
| `message` | エラーメッセージ (空文字=成功) |
| `results` (sync) / `segments` (async) | 認識結果の配列 |

### Token 構造 (`results[].tokens[]`)

| フィールド | 内容 |
|---|---|
| `written` | 表記 (例: "今日") |
| `spoken` | 読み (日本語: ひらがな、中国語: ピンイン) |
| `starttime` | 開始時刻 (ms) |
| `endtime` | 終了時刻 (ms) |
| `confidence` | 信頼度 (0-1) |
| `label` | 話者ラベル (diarization 有効時のみ) |

## ベストプラクティス

| 推奨 | 理由 |
|---|---|
| **API キーをログに出さない** | セキュリティ |
| **`loggingOptOut=True` を検討** | 機密音声を扱う場合 |
| **polling 間隔は 2-10 秒** | サーバ負荷と応答性のバランス |
| **失敗時は指数バックオフ** | 一時的なネットワーク障害に対応 |
| **音声フォーマットは WAV / 16kHz / モノラル / 16bit** | エンジン最適値 |
| **音声は 1-2 分以下が扱いやすい** | 長尺は分割推奨、無料枠管理にも有利 |

## 関連リンク

- API マニュアル: https://docs.amivoice.com/
- 英語版マニュアル: https://docs.amivoice.com/en/
- リクエストパラメータ: https://docs.amivoice.com/en/amivoice-api/manual/request-parameters/
- 結果フォーマット: https://docs.amivoice.com/en/amivoice-api/manual/result-format/
- 同期 HTTP: https://docs.amivoice.com/amivoice-api/manual/reference-sync-http/
- 非同期 HTTP: https://docs.amivoice.com/amivoice-api/manual/reference-async-http/
- WebSocket: https://docs.amivoice.com/amivoice-api/manual/reference-websocket/
