"""Streamlit UI for speech-habit-lens.

Launched via `shl serve` (which subprocess-runs `streamlit run` on this file).
The UI calls the same recognize/analyze/report core as the CLI, so behavior
stays consistent between CLI and browser.

API keys are read server-side from .env — they are never exposed to the
browser.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from speech_habit_lens.analyze import analyze as run_analysis
from speech_habit_lens.esas import ESAS_PARAMS, EsasTimeline, parse_esas
from speech_habit_lens.recognize import recognize
from speech_habit_lens.report import to_markdown

load_dotenv()


DEFAULT_PARAMS = ("energy", "stress", "concentration")


def main() -> None:
    st.set_page_config(
        page_title="speech-habit-lens",
        page_icon="🎙",
        layout="wide",
    )

    st.title("speech-habit-lens")
    st.caption("1分間スピーチの癖を AmiVoice ESAS × Claude で可視化")

    with st.sidebar:
        st.header("設定")
        model = st.selectbox(
            "Claude model",
            options=["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"],
            index=0,
        )
        use_esas = st.checkbox("ESAS (感情分析) を有効化", value=True)
        st.divider()
        st.caption(
            "AmiVoice / Anthropic の API key は `.env` から server 側で読み込まれます。"
            "ブラウザには露出しません。"
        )

    uploaded = st.file_uploader(
        "WAVファイルをアップロード（16kHz/mono推奨、30-90秒）",
        type=["wav"],
        help="長さ 30〜90秒、サンプリングレート 16kHz, モノラル, 16-bit PCM を推奨",
    )

    if uploaded is None:
        st.info(
            "WAVファイルをアップロードしてください。"
            "サンプルがない場合は `tools/fetch_speech.sh` で取得できます "
            "（`examples/CREDITS.md` 参照）。"
        )
        return

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(uploaded.read())
        wav_path = Path(tmp.name)

    st.audio(uploaded.getvalue(), format="audio/wav")

    if not st.button("🔍 解析を開始", type="primary"):
        return

    try:
        _render_analysis(wav_path, model=model, use_esas=use_esas)
    finally:
        wav_path.unlink(missing_ok=True)


def _render_analysis(wav_path: Path, *, model: str, use_esas: bool) -> None:
    with st.status("AmiVoice で音声認識中...", expanded=False) as status:
        rec = recognize(wav_path, esas=use_esas)
        status.update(
            label=f"✓ 認識完了 ({rec.duration_ms / 1000:.1f}s, {len(rec.segments)} segments)",
            state="complete",
        )

    esas = parse_esas(rec.raw_response)
    if use_esas:
        st.caption(f"ESAS: {len(esas.samples)} samples")

    with st.status(f"Claude ({model}) で3層解析中...", expanded=False) as status:
        analysis = run_analysis(rec, esas, model=model)
        status.update(label="✓ 3層解析完了", state="complete")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("認識テキスト")
        for s in rec.segments:
            with st.container(border=True):
                t_start = s.start_ms / 1000
                t_end = s.end_ms / 1000
                st.markdown(f"**[{t_start:.1f}s – {t_end:.1f}s]**　_(conf={s.confidence:.2f})_")
                st.write(s.text)

    with col_right:
        st.subheader("ESAS 時系列")
        if esas.samples:
            _render_esas_chart(esas)
        else:
            st.info("ESAS データなし（`--no-esas` 指定 or 音量が小さすぎる）")

    st.divider()

    st.subheader("⭐ クロス層 — 身体 × 言葉の連動")
    patterns = analysis.cross.get("patterns", [])
    if patterns:
        for i, p in enumerate(patterns, 1):
            e = p.get("evidence", {})
            with st.expander(f"#{i} {p.get('name', '?')}", expanded=True):
                st.markdown(f"- **時刻**: {e.get('second', 0):.1f}s")
                st.markdown(
                    f"- **ESAS**: `{e.get('esas_param', '?')}` = "
                    f"**{e.get('esas_value', '?')}**"
                )
                st.markdown(f"- **引用**: 「{e.get('text_quote', '')}」")
                st.markdown(f"- **意味**: {p.get('significance', '')}")
    else:
        st.caption("クロスパターンの抽出結果なし")

    st.subheader("改善提案")
    improvements = analysis.cross.get("improvements", [])
    for i, imp in enumerate(improvements, 1):
        grounded = ", ".join(imp.get("grounded_in", []))
        st.markdown(f"**{i}. {imp.get('suggestion', '')}**")
        if grounded:
            st.caption(f"根拠: {grounded}")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("音響層 概要")
        ac = analysis.acoustic
        st.markdown(f"- **冒頭**: {ac.get('opening_signature', '—')}")
        st.markdown(f"- **終端**: {ac.get('closing_signature', '—')}")
        for h in ac.get("habits", []):
            st.markdown(f"- **{h.get('name', '?')}** — {h.get('description', '')}")

    with col2:
        st.subheader("テキスト層 概要")
        tx = analysis.text
        fillers = tx.get("fillers", [])
        if fillers:
            f_str = "、".join(f'"{f["word"]}" ({f["count"]})' for f in fillers)
            st.markdown(f"- **フィラー**: {f_str}")
        cp = tx.get("conclusion_position", {})
        if cp:
            st.markdown(
                f"- **結論位置**: {cp.get('zone', '?')} "
                f"(~{cp.get('evidence_second', 0):.1f}s)"
            )
        st.markdown(f"- **冒頭フック**: {tx.get('opening_hook', '—')}")
        st.markdown(f"- **終端**: {tx.get('closing_landing', '—')}")

    st.divider()

    report_md = to_markdown(analysis)
    st.download_button(
        "📄 レポートをダウンロード（.md）",
        data=report_md.encode("utf-8"),
        file_name=f"speech_report_{rec.session_id[:12]}.md",
        mime="text/markdown",
    )

    with st.expander("📝 フル Markdown レポートをプレビュー"):
        st.markdown(report_md)


def _render_esas_chart(esas: EsasTimeline) -> None:
    selected = st.multiselect(
        "表示パラメータ",
        options=list(ESAS_PARAMS),
        default=list(DEFAULT_PARAMS),
        help="複数選択可。デフォルトは energy / stress / concentration の3指標",
    )
    if not selected:
        st.caption("パラメータを1つ以上選択してください")
        return

    fig = go.Figure()
    for p in selected:
        series = esas.series(p)
        xs = [t / 1000 for t, _ in series]
        ys = [v for _, v in series]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=p))

    fig.update_layout(
        xaxis_title="時間 (秒)",
        yaxis_title="値 (0-100)",
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=40, r=20, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
