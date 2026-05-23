# Prompt Version Log

## v0.1 (2026-05-23)

最初の三層プロンプト設計。

### 設計上の判断

- **三層構成の理由**: 全データを単一プロンプトに渡すと、Claude の attention が散ってクロスパターンの精度が落ちる。音響 / テキスト / クロス で分けることで、各層の入力面積を最小化し、精度を上げる。

- **JSON-only 出力**: `analyze.py` / `report.py` での後続マージを容易にするため。クロス層は前2層の JSON を入力として受け取れる。

- **Grounding Rule**: 時刻・パラメータ・引用の3点引用を必須にしてハルシネーション抑制。`harness-engineering-guide` ch6 のグラウンディング手法を参考。

- **ESAS 20 パラメータの完全列挙**: 2026-05-23 に AmiVoice live API で実測確認。公式 docs に記載されていた 5 つ（energy/stress/uncertainty/concentration/anticipation）以外の 15 つもプロンプト内に明示し、Claude がパラメータ名を取り違えるリスクを除去。

### チューニング履歴

- **2026-05-23 v0.1**: 初版。Stallman 60秒で初回 E2E。
  - acoustic / text / cross すべて完走、stop=end_turn
  - cross_layer 出力 2,429 tokens（max_tokens=4096 に対し余裕あり）
  - 観察品質は高いが、各 pattern の significance が 200-300字と冗長

- **2026-05-23 v0.1.1**: 冗長性を削減（v0.1 出力レビューから）
  - acoustic.habits: 「3-5個」→「ちょうど3個」、description 2文以内150字
  - cross.patterns: 「3-5個」→「ちょうど3個」、significance 1文100字
  - cross.improvements: 「2-3個」→「ちょうど2個」、suggestion 1文80字
  - 狙い: 読み手の認知負荷を下げて、最も鋭い観察に集中させる

### 今後の検討項目

- Sonnet 4.6 で安定するか、Opus 4.7 を使う価値があるか（コスト3倍 vs クロスパターン質）
- 言語別プロンプト分離（日本語 / 英語）が必要か
- Few-shot 例の追加（特に cross_layer の「良い observation 例」）
