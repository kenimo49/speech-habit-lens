# 4本の名スピーチを 1分ずつ解析した比較

speech-habit-lens の動作検証および ESAS パラメータの実測知見として、公開されている4本の著名スピーチを各1分ずつ解析した結果を比較する。

## 解析対象

すべて YouTube 上の公開動画から、`yt-dlp` で1分セクションを切り出して解析した（音声ファイル自体は本リポジトリには含めない — `data/private/` 配下に gitignore で管理）。

| 動画 | 切り出し範囲 | アップロード元 |
|---|---|---|
| **Steve Jobs - Stanford Commencement Address (2005)** | 14:00–15:00（"Stay hungry, stay foolish" 部分） | Stanford 公式チャンネル |
| **孫正義 - 新30年ビジョン (2010)・第10章「情報革命で人々を幸せに」** | 0:00–1:00（冒頭セクション） | SoftBank Group 公式チャンネル |
| **西野亮廣 - 講演会 in ホーチミン** | 0:00–1:00（冒頭セクション） | 西野亮廣 公式チャンネル |
| **落合陽一 - TEDxTokyo 2014「Physicalization of Computer Graphics」** | 0:00–1:00（冒頭セクション） | TEDx Talks 公式チャンネル |

## 比較表

| 指標 | Jobs終盤 | 孫正義冒頭 | 西野冒頭 | 落合冒頭 |
|---|---|---|---|---|
| **energy** peak | 21 | **44** | 32 | 39 |
| **concentration** peak | 100 | 100 | 90 | 100 |
| **anticipation** peak | 68 | **100** | 35 | 91 |
| **emo_cog** peak | 207 | 136 | **276** | 244 |
| **passionate** peak | 6 | 4 | **11** | 8 |
| **結論位置** | back | **front** | middle | back |
| **フィラー** | "ね"×1 | "ね"×1 | **"ちょっと"×5 + "なと"×3** | "あの"×1 |
| **認識精度** | conf 0.74–0.89（英語×日本語エンジン） | **0.99–1.00**（完璧） | 0.93–1.00（完璧） | 0.70–0.82（日英混在） |

> **値域の注意**: `emo_cog`（Emotional-Balanced-Logical）は仕様上 0–300 程度の値域。他のパラメータ（0–100）と比較してそのまま読まない。100超は仕様内の正常値。

## 各話者の核となる癖

### Steve Jobs（Stanford 終盤・"Stay hungry, stay foolish"）
- 「passionate=平均0.7、peak=6（クライマックス瞬間）」— **熱量は数値上は出ない**、ただし concentration peak 100 で「静かに語る確信スタイル」が観察される
- 認識テキストは英語×日本語エンジンで誤認識まみれだが、ESAS は言語非依存で機能。「ステイフーリッシュ」だけは部分的にカタカナで残った
- 結論ゾーン（56–59s）で confidence=27→ 残存、passionate=6→0 → 確信なき着地として収束感を欠く

### 孫正義（新30年ビジョン 冒頭・「情報革命で人々を幸せに」）
- **結論を冒頭に置く**（1.8s で concentration=100 / 14.7s で anticipation=100 / 16.3s で energy=44 スパイク）
- 中盤の「30年後」反復で energy=1〜2 まで低迷 — リフレインしながら声量が落ちる
- 終端は「思うかもしれません、あるいは思わないかもしれません」で両論留保 → 冒頭で宣言した強い主張が終端で失圧
- **典型的な日本式構成**: 強い主張先出し → 詳細淡々 → 余韻型クロージング

### 西野亮廣（ホーチミン講演 冒頭）
- **フィラー "ちょっと"×5、"なと"×3** — 他3人が「ね/あの」1回程度なのに対し、定量的に多い
- hesitation=12–21 が全25サンプルで持続 → 躊躇が語彙レベル（フィラー）と音声レベル（hesitation）で **二重固定**
- 終幕の無音区間（45.4s〜）で energy=32、emo_cog=276、confidence=30 と全スピーチ最高値 → 「伝えたい熱量が言葉を持つ場面でなく場の終息後に放出」

### 落合陽一（TEDxTokyo 2014 冒頭）
- 39.9s で **concentration=100, stress=35, confidence=2 が同時発生** — 「全力で考えているが自分の言葉に確信が持てない」矛盾
- 39.1s で anticipation=91 のスパイク、同区間で認識テキストが日英混在に崩壊 → 「身体の高揚が言葉の構造を追い越して空回り」
- 早口で英語混じりの話し方がデータに反映される（認識精度 conf 0.70–0.82）

## 横断的に見えた知見

### 1. 「身体と言葉のラグ」は4人全員に共通
energy / concentration / anticipation の peak と、発話内容（テキスト層が捉えた主張位置）が一致しないパターンが4人全員で観察された。これは ESAS × テキストレイヤーのクロス解析だけで見える現象。

### 2. 構成パターンの違い
- **front 型（孫正義）**: 結論先出し → 詳細 → 余韻
- **middle 型（西野）**: 前置き → 依頼/主張 → フェード
- **back 型（Jobs / 落合）**: 詳細展開 → 終盤に主張

### 3. フィラーの個性が定量化された
他3人が "ね/あの" 1回程度に対して、西野だけ "ちょっと" 5回 + "なと" 3回。これは「西野節」として観察可能な癖。

### 4. `passionate` は全員低い（peak 4–11）
「熱い」と感じる4人だが、AmiVoice の `passionate` 指標は別の何か（より特定の音響特徴）を測っている可能性。「観察者の主観的熱量」と「音響パラメータの passionate」は別物として扱うべき。

### 5. 認識テキストが誤認識でも ESAS は機能する
Jobs（英語×日本語エンジン）、落合（日英混在）でも ESAS パラメータは意味のある値を出した。**「言葉が分からなくても、声の癖は分かる」** がツールの価値の一つ。

## このケーススタディから出た改善ポイント

| 発見 | 反映先 |
|---|---|
| `emo_cog` の値域は 0–300（公式 doc サンプル `Emotional-Balanced-Logical: 250` で確認） | `prompts/acoustic_layer.md` に値域明記、Claude が「異常」と誤判定しないよう改修 |
| フィラー検出が日本語の終助詞「ね」を拾う | `prompts/text_layer.md` でフィラー定義を厳密化、終助詞は除外 |
| 並列実行時に `/tmp/shl-{layer}.txt` が上書きされる | `analyze.py` で per-process ディレクトリ（pid + timestamp）に変更 |
| `text_layer` が確率的に JSON パース失敗 | `analyze.py` で stop_reason=end_turn 時に1回自動 retry |
| polling 中の無音 | `recognize.py` で 10秒おきに INFO ログ |

これらは v0.1.2 として個別 commit で反映済み（git log 参照）。

## 再現方法

```bash
# 各動画を取得（個人ローカル分析用、リポジトリには含めない）
yt-dlp \
  --download-sections "*14:00-15:00" \
  -x --audio-format wav \
  --postprocessor-args "ffmpeg:-ac 1 -ar 16000 -sample_fmt s16" \
  -o "data/private/youtube/jobs-finale.%(ext)s" \
  "https://www.youtube.com/watch?v=UF8uR6Z6KLc"

# 解析
.venv/bin/shl analyze data/private/youtube/jobs-finale.wav \
  --out data/private/reports/jobs-finale.md
```

`data/private/` 配下は `.gitignore` 対象。著作権 / YouTube ToS の観点から、音声ファイルおよびレポート全文は本リポジトリには含めない。本ドキュメントには **解析結果から抽出した観察と知見のみ** を掲載している。
