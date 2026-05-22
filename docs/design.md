# Architecture & Design

> このドキュメントは speech-habit-lens の **エンジニアリング設計書**。
> プロジェクト進捗・意思決定の追跡は [Issue #1](https://github.com/kenimo49/speech-habit-lens/issues/1) で行う。

## 1. System Overview

speech-habit-lens は、1分間スピーチの `.wav` ファイルを入力に、**音響層 × テキスト層 × クロス層** の三層解析を経てMarkdownレポートを出力する CLI ツール。

```
        ┌──────────────┐    ┌──────────────────┐
        │ CLI (shl)    │    │ Streamlit UI     │
        │ shl analyze  │    │ shl serve        │
        └──────┬───────┘    └────────┬─────────┘
               │                     │
               └─────────┬───────────┘
                         ▼
                 ┌──────────────────┐
                 │  analyze()       │  ← 共通コア
                 └────────┬─────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │  AmiVoice 非同期HTTP │
               │  ?d=-a-general      │
   .wav ─────▶│  +sentiment=True    │──┬─▶ text + timestamps
               │                     │  └─▶ 20 emotion params × ~30 samples
               └─────────────────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │   Claude (3 calls)  │
               │  ・acoustic_layer   │
               │  ・text_layer       │
               │  ・cross_layer ⭐   │ 差別化の核
               └─────────────────────┘
                          │
                          ▼
               ┌─────────────────────┐
               │  report.py          │ Markdown生成
               └─────────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        report.md (CLI)      Web UI 表示 + DL
                             (Streamlit, plotly チャート)
```

**設計原則**: CLI と Streamlit UI は **同じ `analyze()` コア関数を呼ぶ薄いプレゼンテーション層**。重複ロジック禁止。

## 2. Key Constraints (実装に効く制約)

| 制約 | 出典 | 設計への影響 |
|---|---|---|
| **ESAS は非同期HTTPでのみ利用可** | AmiVoice公式 | 同期HTTPは捨て、非同期一本化。ジョブ submit → polling パターン |
| **ESAS 出力は約2秒間隔** | AmiVoice公式 | 60秒スピーチで約30サンプル。LLM に渡す JSON サイズ < 4KB |
| **無料枠は月60分 (全エンジン共通)** | AmiVoice公式 | デフォで1解析 = 1分以下を強制。`--max-duration 60` チェック |
| **ESAS 20パラメータの正式名は要API確認** | 公式docには5例のみ (喜び/憤り/ストレス/不満/期待) | 初回API呼び出しでフィールド名を取得し、`docs/esas-params.md` に書き起こす |
| **Claude API tokens は1解析で推定 5-10k input + 1-2k output** | 内部見積もり | コストは1解析 $0.05〜$0.10 程度 (Sonnet 4.6想定) |

## 3. Module Responsibilities

| モジュール | 責務 | 公開 API |
|---|---|---|
| `recognize.py` | AmiVoice 非同期 HTTP の薄いラッパー。ジョブ submit + polling + 結果取得 | `recognize(wav_path, *, esas=True) -> RecognitionResult` |
| `esas.py` | ESAS JSON を時系列構造体に整形。20パラメータの抽出と派生統計 (mean/peak/slope) | `parse_esas(raw) -> EsasTimeline` |
| `analyze.py` | Claude API を3回呼ぶ。各層プロンプトを `prompts/` から読み込み、結果をマージ | `analyze(rec_result, esas_timeline) -> Analysis` |
| `report.py` | `Analysis` を Markdown に整形。タイムスタンプ引用付き | `to_markdown(analysis) -> str` |
| `cli.py` | `click` ベースのCLI、`shl analyze` / `shl serve` / `shl compare` (v0.2) | `main()` |
| `webui.py` | Streamlit UI。ローカルブラウザで動作、`analyze()` を呼んで Plotly チャート + レポート表示 | `streamlit_app()` |

### 依存方向

```
cli.py ──▶ analyze.py ──▶ recognize.py
   │          │              │
   │          │              └──▶ esas.py
   │          ▼
   │       report.py
   │
   └──▶ webui.py ──▶ analyze.py  (cliとwebuiは互いを呼ばない)
```

逆方向の依存は禁止 (`recognize.py` から `report.py` を呼ばない等)。CLI と Streamlit UI は **どちらも analyze() の利用者**であり、互いに依存しない。

## 4. Data Flow

### 4.1 入力 (Audio Spec)

- フォーマット: WAV (PCM, 16-bit)
- サンプリングレート: 16kHz 推奨 (AmiVoice general engine の最適値)
- チャンネル: モノラル
- 長さ: 30〜90秒 (推奨60秒)
- 上限: 60秒超は警告、120秒超は拒否 (無料枠を即座に食い潰さないため)

### 4.2 中間データ構造

```python
@dataclass
class RecognitionResult:
    text: str                          # 全文
    segments: list[Segment]            # タイムスタンプ付き発話単位
    raw_response: dict                 # AmiVoice JSON 全体 (デバッグ用)

@dataclass
class Segment:
    start_ms: int
    end_ms: int
    text: str
    confidence: float

@dataclass
class EsasTimeline:
    samples: list[EsasSample]          # ~30点
    duration_ms: int

@dataclass
class EsasSample:
    timestamp_ms: int
    params: dict[str, float]           # 20 emotion parameters
```

### 4.3 出力 (Report Format)

Markdown レポート構造:

```markdown
# Speech Habit Analysis — {filename}
**Duration:** 62.3s | **Words:** 198 | **Generated:** 2026-05-22 20:15

## 認識テキスト
> [00:00] こんにちは、〇〇です。今日は…
> [00:08] えーと、3つお話しします…
> ...

## 音響層 (ESAS)
- 出だしのテンション: ◯
- 中盤のエネルギー失速: 28-42秒で `期待` が30%減
- 終端: `ストレス` 急上昇 (締めの不安?)

## テキスト層
- フィラー: "えーと" 8回、"あの" 5回
- 結論位置: 52秒 (全体の84%地点) ← 後置型
- 繰り返し語: "重要" 6回

## クロス層 ⭐
1. **結論前に声量が落ちる** — 48-52秒で `期待` が低下しつつ "重要なのは…" と切り出している
2. ...

## 改善提案
1. 結論を冒頭30秒以内に持ってくる
2. ...
```

## 5. AmiVoice Integration

### 5.1 認証

```bash
# .env
AMIVOICE_API_KEY=xxxxxxxxxx
```

API キーは form parameter `u` で送る (公式仕様)。Header ではない。

### 5.2 非同期HTTP フロー

```
POST /v1/recognitions      # ジョブ submit、sessionid 取得
  ↓ (polling, 2-10s 間隔)
GET  /v1/recognitions/{id}  # status=completed まで待つ
  ↓
GET  /v1/recognitions/{id}  # 完了時のレスポンスから text + ESAS 抽出
```

### 5.3 ESAS 有効化

```
POST /v1/recognitions
  -F u=$API_KEY
  -F d=-a-general
  -F a=@speech.wav
  -F speakerDiarization=False
  -F sentimentAnalysis=True    # ← ESAS 有効化フラグ (要確認)
```

実装時に公式ドキュメントで `sentimentAnalysis` パラメータ名と値を確認すること。

### 5.4 リトライ・タイムアウト

- ジョブ submit 失敗: 3回まで指数バックオフ (2s, 4s, 8s)
- polling 上限: 300秒 (60秒音声に対して 5x 余裕)
- 429 (rate limit): 60秒待機後リトライ

## 5.5 Streamlit UI 仕様 (v0.1)

CLI と並ぶ第二プレゼンテーション層。`shl serve` でブラウザを起動し、`.wav` をドロップして解析する。

### 起動

```bash
shl serve                  # localhost:8501 で起動
shl serve --port 9999     # ポート指定
```

内部実装は `streamlit run src/speech_habit_lens/webui.py` を `subprocess` で呼ぶ薄いラッパー。

### UI 構成

```
┌───────────────────────────────────────────────────┐
│ speech-habit-lens                          [help] │
├───────────────────────────────────────────────────┤
│ [📁 Upload .wav]  または [🎙 Record (v0.2)]       │
├───────────────────────────────────────────────────┤
│ Recognition Text          | ESAS Time Series      │
│ [00:00] こんにちは…       | (Plotly 折れ線3本:    │
│ [00:05] 今日は…           |  Energy/Stress/EBL)   │
│ …                         |                       │
├───────────────────────────────────────────────────┤
│ ## 観察された癖 (LLM出力)                          │
│ 1. 結論前に声量が落ちる…                          │
│ …                                                 │
├───────────────────────────────────────────────────┤
│ [⬇ Download report.md]  [📋 Copy to clipboard]    │
└───────────────────────────────────────────────────┘
```

### 採用ライブラリ

| ライブラリ | 用途 |
|---|---|
| `streamlit` | UI フレームワーク |
| `plotly` | ESAS 20パラメータの時系列チャート (zoom/hover 対応) |
| `python-dotenv` | `.env` から API key 読み込み (CLIと共通) |

### API key の扱い

- ユーザーの `.env` から読み込む (公開ホスティング想定外)
- 環境変数未設定なら UI 上に明示エラー
- ブラウザに API key を露出させない (server 側で完結)

## 6. LLM Prompt Architecture

### 6.1 3層構成の理由

1層 (cross_layer のみ) でも動くが、Claude のコンテキスト効率と解析品質のため層を分割:

- **音響層**: ESAS JSON だけ渡し、感情パラメータの時系列特徴を抽出
- **テキスト層**: テキスト+セグメントだけ渡し、構造・語彙の癖を抽出
- **クロス層**: 上記2層の出力 + 元データを統合し、身体×言語の連動を発見 ⭐

3層に分けることで:
- 各 prompt のコンテキストが軽くなり、precision が上がる
- クロス層は前2層の "観察結果"を入力に持つので、より深い解析ができる
- 失敗した層だけリトライ可能

### 6.2 プロンプトの保管とバージョン

```
prompts/
├── acoustic_layer.md   # 音響層プロンプト本体
├── text_layer.md       # テキスト層プロンプト本体
├── cross_layer.md      # クロス層プロンプト本体 ⭐ 差別化の核
└── _version.md         # プロンプトの履歴・思想・チューニングログ
```

全プロンプトは Markdown で公開。隠す価値より公開してフィードバックを受ける価値が大きい (`avoid-ai-writing` / `harness-ops` と同方針)。

### 6.3 ハルシネーション対策

各プロンプトの末尾に共通の "Grounding Rule" を入れる:

```
## Grounding Rule
- 出力には必ず入力データ内のタイムスタンプ or テキスト引用を含めること
- 入力に存在しない発話・パラメータ値を引用してはならない
- 「だろう / 思われる」等の推測表現は使わず、データに基づいた断定で書く
```

## 7. Error Handling Strategy

| エラー | 対応 |
|---|---|
| 音声ファイル読み込み失敗 | 即 exit、明確なエラーメッセージ |
| AmiVoice 401 (auth) | 即 exit、`.env` 確認を促す |
| AmiVoice 429 (rate limit) | 60秒待機 + リトライ |
| AmiVoice 5xx | 3回までリトライ後 exit |
| polling timeout | エラーとして exit、ジョブ ID を表示し再開可能に |
| Claude API 失敗 | レイヤごとリトライ。3層中1層失敗時はその層を欠落させて報告 |
| ESAS パラメータが空 | "ESAS データが取得できませんでした" を report に明記し、テキスト層+クロス層は通常通り |

## 8. Privacy & Data Handling

- 音声ファイルはユーザーローカルに留める。AmiVoice 以外へは送らない
- AmiVoice のデータ保持ポリシーを README に明記
- Claude には テキスト + ESAS JSON のみ送る (音声バイナリは送らない)
- `--dry-run` オプションで Claude 送信前に内容確認可能
- ログにAPIキーを書き出さない (`.gitignore` でログディレクトリ除外)

## 9. Extension Points (v0.2/v1.0で広げる箇所)

| 拡張 | 触る場所 |
|---|---|
| before/after 比較 | `cli.py` / `webui.py` に compare モード、`report.py` に diff renderer |
| HTML/PDF出力 | `report.py` に renderer インタフェース、weasyprint等を別 deps に |
| ブラウザ録音 | `webui.py` に `streamlit-audiorecorder` 等の component 追加 |
| 多言語対応 (EN) | `prompts/` を `prompts/ja/` `prompts/en/` に分割、`--lang` フラグ |
| リアルタイム解析 | `recognize.py` の隣に `recognize_stream.py`、WebSocket実装 |

## 10. テスト戦略 (v0.2 以降)

- **Unit**: `esas.py` の time series 処理、`report.py` の markdown 生成
- **Integration**: AmiVoice API mock (`pytest-httpx`)、Claude mock
- **E2E**: `examples/ken-before.wav` を入力に既知の report と diff チェック

v0.1 では手動E2E (`shl analyze examples/sample.wav` の目視確認) のみ。

## 11. 参考資料

### 内部ドキュメント

- **[Knowledge Base](./knowledge/README.md)** — AmiVoice 関連ドキュメントのインデックス
  - [AmiVoice Overview](./knowledge/amivoice-overview.md) — サービス全体像、エンジン、価格
  - [AmiVoice API Reference](./knowledge/amivoice-api-reference.md) — 3インタフェース、パラメータ、レスポンス
  - [AmiVoice ESAS](./knowledge/amivoice-esas.md) — 感情分析 20パラメータ完全リファレンス
- [Issue #1 (Project tracking)](https://github.com/kenimo49/speech-habit-lens/issues/1) — 進捗・意思決定

### 外部リソース

- [AmiVoice API 公式](https://acp.amivoice.com/main/)
- [AmiVoice API マニュアル](https://docs.amivoice.com/)
- [ESAS (感情分析) サービス](https://acp.amivoice.com/main/service/esas/)
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
