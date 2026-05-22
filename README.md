# speech-habit-lens

> 1分間スピーチの癖を、AmiVoice ESAS (感情20パラメータ) × LLM の三層解析で可視化するCLIツール。

**Status: v0.1 development (Zennfes Spring 2026 提出予定)**

## なぜこのツール

1分間スピーチ・ピッチ・自己紹介は誰もが繰り返す場面なのに、自分の「癖」を客観視できる手段が乏しい。本ツールは:

- 音響層 (ESAS) — テンション推移・抑揚の偏り・出だしのエネルギー
- テキスト層 (LLM) — フィラー・結論位置・語彙の偏り
- クロス層 (LLM 統合) — 「結論手前で声量が落ちる」等の身体×言語連動

の三層で1分スピーチの癖をMarkdownレポート化する。

## クイックスタート

```bash
git clone https://github.com/kenimo49/speech-habit-lens
cd speech-habit-lens
cp .env.example .env
# .env に AMIVOICE_API_KEY と ANTHROPIC_API_KEY を記入
pip install -e .

# CLI で解析
shl analyze examples/sample.wav --out /tmp/report.md

# ブラウザ UI で解析 (Streamlit、ローカル起動)
shl serve
# → http://localhost:8501 が開く、wav をドロップして解析
```

## 使い方

### CLI

```bash
# 1本解析
shl analyze my-pitch.wav --out reports/2026-05-22.md

# before/after 比較 (v0.2)
shl compare before.wav after.wav
```

### Streamlit UI

```bash
shl serve                    # localhost:8501 で起動
shl serve --port 9999       # ポート指定
```

ローカルで動作するので API key はブラウザに露出しない。`.env` から server 側で読み込む。

## 必要なAPIキー

| サービス | 用途 | 無料枠 |
|---|---|---|
| [AmiVoice API](https://acp.amivoice.com/main/) | 音声認識 + ESAS感情分析 | 月60分/全エンジン |
| [Anthropic API](https://console.anthropic.com/) | LLM解析 (Claude) | クレジット制 |

AmiVoiceは月60分を超えると ¥79.2/hr の従量課金。1解析あたり1分なので、月60本までは実質無料で運用できる。

## ライセンス

MIT
