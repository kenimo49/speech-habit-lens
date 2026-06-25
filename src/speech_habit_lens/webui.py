"""Streamlit UI for speech-habit-lens.

Launched via `shl serve` (which subprocess-runs `streamlit run` on this file).
The UI calls the same recognize/analyze/report core as the CLI, so behavior
stays consistent between CLI and browser.

API keys are read server-side from .env — they are never exposed to the
browser.
"""

from __future__ import annotations

import shutil
import subprocess
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


def _to_amivoice_wav(src_bytes: bytes, src_suffix: str) -> Path:
    """Normalize arbitrary audio bytes to AmiVoice spec (16kHz mono 16-bit PCM)."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg not found in PATH. Install via `apt install ffmpeg`.")
    src = Path(tempfile.mkstemp(suffix=src_suffix)[1])
    src.write_bytes(src_bytes)
    dst = Path(tempfile.mkstemp(suffix=".wav")[1])
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src),
                "-ac", "1", "-ar", "16000", "-sample_fmt", "s16",
                str(dst),
            ],
            check=True,
            capture_output=True,
        )
    finally:
        src.unlink(missing_ok=True)
    return dst


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

    tab_record, tab_upload = st.tabs(["🎙 録音する", "📁 ファイルをアップロード"])

    wav_path: Path | None = None
    audio_preview: bytes | None = None
    audio_preview_format = "audio/wav"

    with tab_record:
        st.caption(
            "ブラウザで直接録音します。60秒前後を目安に録音してください。"
            "停止後に自動で AmiVoice 仕様（16kHz / mono / 16-bit PCM）に変換します。"
        )

        st.components.v1.html(
            """
<div style="font-size:13px; margin-bottom:8px;">
  下の録音widgetが使うマイク:
  <span id="shl-default-mic" style="font-weight:600;">取得中...</span>
</div>
<script>
(async () => {
  const target = document.getElementById('shl-default-mic');
  try {
    let granted = false;
    if (navigator.permissions && navigator.permissions.query) {
      try {
        const perm = await navigator.permissions.query({name: 'microphone'});
        granted = (perm.state === 'granted');
      } catch (_) {}
    }
    if (!granted) {
      try {
        const probe = await navigator.mediaDevices.getUserMedia({audio: true});
        probe.getTracks().forEach(t => t.stop());
        granted = true;
      } catch (e) {
        target.textContent = '未取得（録音ボタンを一度押して権限付与してください）';
        return;
      }
    }
    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
    const label = stream.getAudioTracks()[0].label || '(no label)';
    stream.getTracks().forEach(t => t.stop());
    target.textContent = label;
  } catch (e) {
    target.textContent = '取得失敗: ' + e.message;
  }
})();
</script>
""",
            height=40,
        )

        with st.expander("別のマイクに切り替える手順（Chrome）"):
            st.markdown(
                "**方法A: グローバル既定マイクを変える（手早い）**\n\n"
                "1. 下のURLをコピーしてアドレスバーに貼り付け（chrome:// URLはクリックでは開けない）:\n"
            )
            st.code("chrome://settings/content/microphone", language=None)
            st.markdown(
                "2. ページ上部の **マイク** ドロップダウンから使いたいデバイスを選ぶ\n"
                "3. このページに戻って **Ctrl+Shift+R** でハードリロード\n\n"
                "**方法B: このサイトだけ切替（他サイトに影響なし）**\n\n"
                "1. アドレスバー左の鍵アイコンをクリック\n"
                "2. **サイトの設定** を開く\n"
                "3. **マイク** のドロップダウンから使いたいデバイスを選ぶ\n"
                "4. ハードリロード（Ctrl+Shift+R）"
            )

        rec_audio = st.audio_input(
            "下の丸いマイクボタンを押すと録音開始 / もう一度押すと停止",
            key="shl_mic",
            help="ボタンを押すとブラウザがマイク権限を要求します。許可後、再度ボタンを押すと録音開始します。",
        )

        with st.expander("録音が無音になるとき / デバイス指定テスト"):
            st.caption(
                "マイクから本当に音が来ているか、別デバイスで動作確認できます。"
                "ここのテストは録音widgetとは独立で、デバイスIDを指定して動作確認するためのものです。"
            )
            st.components.v1.html(
                """
<div style="margin-bottom:8px;">
  <button id="shl-list-devices" style="padding:6px 12px; cursor:pointer; margin-right:6px;">
    デバイス一覧を読み込む
  </button>
  <select id="shl-device" style="padding:6px; margin-right:6px; min-width:280px;">
    <option value="">(ブラウザ既定)</option>
  </select>
</div>
<div style="margin-bottom:8px;">
  <button id="shl-meter" style="padding:6px 12px; cursor:pointer; margin-right:6px;">
    音声レベル測定 (10秒)
  </button>
  <button id="shl-rec-test" style="padding:6px 12px; cursor:pointer;">
    5秒テスト録音
  </button>
</div>
<div id="shl-level-bar" style="height:8px; background:#e3dfd2; border-radius:2px; margin-bottom:8px; overflow:hidden;">
  <div id="shl-level-fill" style="height:100%; width:0%; background:#1e3a8a; transition:width 0.05s;"></div>
</div>
<div id="shl-debug-panel" style="font-family:ui-monospace,monospace; font-size:11px; padding:8px; background:#f0eee8; color:#1a1a2e; max-height:240px; overflow-y:auto; border:1px solid #d4d0c4; border-radius:4px; white-space:pre-wrap;"></div>
<script>
(function(){
  const panel = document.getElementById('shl-debug-panel');
  const fill = document.getElementById('shl-level-fill');
  const log = (msg) => {
    const t = new Date().toLocaleTimeString();
    panel.innerHTML += '[' + t + '] ' + msg + '\\n';
    panel.scrollTop = panel.scrollHeight;
    console.log('[SHL-DEBUG]', msg);
  };

  window.addEventListener('error', (e) => log('window.error: ' + e.message));
  window.addEventListener('unhandledrejection', (e) => log('unhandledrejection: ' + (e.reason && e.reason.message ? e.reason.message : e.reason)));

  log('isSecureContext=' + window.isSecureContext);
  log('UA=' + navigator.userAgent);

  const getConstraints = () => {
    const sel = document.getElementById('shl-device');
    if (sel.value) {
      return {audio: {deviceId: {exact: sel.value}}};
    }
    return {audio: true};
  };

  document.getElementById('shl-list-devices').onclick = async () => {
    try {
      log('デバイス一覧取得');
      const tmp = await navigator.mediaDevices.getUserMedia({audio: true});
      tmp.getTracks().forEach(t => t.stop());
      const devs = await navigator.mediaDevices.enumerateDevices();
      const audio_in = devs.filter(d => d.kind === 'audioinput');
      log('audioinput=' + audio_in.length + '件');
      const sel = document.getElementById('shl-device');
      sel.innerHTML = '<option value="">(ブラウザ既定)</option>';
      audio_in.forEach((d, i) => {
        log('  [' + i + '] ' + d.label);
        const opt = document.createElement('option');
        opt.value = d.deviceId;
        opt.textContent = '[' + i + '] ' + (d.label || '(no label)');
        sel.appendChild(opt);
      });
    } catch(e) {
      log('catch: ' + e.name + ': ' + e.message);
    }
  };

  document.getElementById('shl-meter').onclick = async () => {
    try {
      log('音声レベル測定開始 (10秒、話してください)');
      const stream = await navigator.mediaDevices.getUserMedia(getConstraints());
      const tracks = stream.getAudioTracks();
      log('使用マイク: ' + tracks[0].label);
      const settings = tracks[0].getSettings();
      log('  sampleRate=' + settings.sampleRate + ' channels=' + settings.channelCount);
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const src = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      src.connect(analyser);
      const buf = new Uint8Array(analyser.fftSize);
      const t0 = Date.now();
      let maxRms = 0;
      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / buf.length);
        const pct = Math.min(100, rms * 200);
        fill.style.width = pct + '%';
        if (rms > maxRms) maxRms = rms;
        if (Date.now() - t0 < 10000) {
          requestAnimationFrame(tick);
        } else {
          stream.getTracks().forEach(t => t.stop());
          ctx.close();
          fill.style.width = '0%';
          const verdict = maxRms < 0.001 ? '完全無音（マイクが信号を出していない）'
                        : maxRms < 0.01 ? 'ほぼ無音'
                        : '音声検出 OK';
          log('測定完了 maxRMS=' + maxRms.toFixed(4) + ' → ' + verdict);
        }
      };
      tick();
    } catch(e) {
      log('catch: ' + e.name + ': ' + e.message);
    }
  };

  document.getElementById('shl-rec-test').onclick = async () => {
    try {
      log('5秒テスト録音開始');
      const stream = await navigator.mediaDevices.getUserMedia(getConstraints());
      log('使用マイク: ' + stream.getAudioTracks()[0].label);
      const rec = new MediaRecorder(stream);
      log('MediaRecorder mimeType=' + rec.mimeType);
      const chunks = [];
      rec.ondataavailable = (e) => { chunks.push(e.data); log('chunk size=' + e.data.size); };
      rec.onerror = (e) => log('rec.onerror: ' + e.error);
      rec.onstop = () => {
        const blob = new Blob(chunks, {type: rec.mimeType});
        log('録音完了 blob size=' + blob.size);
        stream.getTracks().forEach(t => t.stop());
      };
      rec.start();
      setTimeout(() => rec.stop(), 5000);
    } catch (e) {
      log('catch: ' + e.name + ': ' + e.message);
    }
  };
})();
</script>
""",
                height=440,
                scrolling=True,
            )
        if rec_audio is not None:
            rec_bytes = rec_audio.getvalue()
            try:
                wav_path = _to_amivoice_wav(rec_bytes, src_suffix=".wav")
                audio_preview = rec_bytes
                audio_preview_format = "audio/wav"
            except (RuntimeError, subprocess.CalledProcessError) as exc:
                st.error(f"音声変換に失敗しました: {exc}")
                return

    with tab_upload:
        uploaded = st.file_uploader(
            "WAVファイルをアップロード（16kHz/mono推奨、30-90秒）",
            type=["wav"],
            help="長さ 30〜90秒、サンプリングレート 16kHz, モノラル, 16-bit PCM を推奨",
        )
        if uploaded is not None and wav_path is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(uploaded.read())
            tmp.close()
            wav_path = Path(tmp.name)
            audio_preview = uploaded.getvalue()
            audio_preview_format = "audio/wav"

    if wav_path is None:
        st.info("録音またはWAVファイルのアップロードを行ってください。")
        return

    if audio_preview:
        st.audio(audio_preview, format=audio_preview_format)

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
    st.plotly_chart(fig, width="stretch")


if __name__ == "__main__":
    main()
