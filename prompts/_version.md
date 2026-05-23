# Prompt Version Log

## v0.1 (2026-05-23)

最初の三層プロンプト設計。

### 設計上の判断

- **三層構成の理由**: 全データを単一プロンプトに渡すと、Claude の attention が散ってクロスパターンの精度が落ちる。音響 / テキスト / クロス で分けることで、各層の入力面積を最小化し、精度を上げる。

- **JSON-only 出力**: `analyze.py` / `report.py` での後続マージを容易にするため。クロス層は前2層の JSON を入力として受け取れる。

- **Grounding Rule**: 時刻・パラメータ・引用の3点引用を必須にしてハルシネーション抑制。`harness-engineering-guide` ch6 のグラウンディング手法を参考。

- **ESAS 20 パラメータの完全列挙**: 2026-05-23 に AmiVoice live API で実測確認。公式 docs に記載されていた 5 つ（energy/stress/uncertainty/concentration/anticipation）以外の 15 つもプロンプト内に明示し、Claude がパラメータ名を取り違えるリスクを除去。

### チューニング履歴

- **2026-05-23 v0.1**: 初版。チューニング未実施。
  - 計測対象: Stallman 60秒（英語）, Stalman は ESAS 27 samples / 3 transcript segments
  - 次回計測: ken本人の日本語1分スピーチを通したときの出力品質

### 今後の検討項目

- Sonnet 4.6 で安定するか、Opus 4.7 を使う価値があるか（コスト3倍 vs クロスパターン質）
- 言語別プロンプト分離（日本語 / 英語）が必要か
- Few-shot 例の追加（特に cross_layer の「良い observation 例」）
