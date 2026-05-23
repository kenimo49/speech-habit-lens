"""Markdown report generator for an Analysis object."""

from __future__ import annotations

from datetime import datetime

from .analyze import Analysis
from .esas import ESAS_PARAMS


def to_markdown(analysis: Analysis) -> str:
    """Render an Analysis as a self-contained Markdown report."""
    rec = analysis.recognition
    esas = analysis.esas
    ac = analysis.acoustic
    tx = analysis.text
    cr = analysis.cross

    duration_s = rec.duration_ms / 1000
    out: list[str] = []

    out.append("# Speech Habit Analysis")
    out.append("")
    out.append(f"- **Duration**: {duration_s:.1f}s")
    out.append(f"- **Transcript length**: {len(rec.text)} chars")
    out.append(f"- **ESAS samples**: {len(esas.samples)}")
    out.append(f"- **Model**: `{analysis.model}`")
    out.append(f"- **Generated**: {datetime.now():%Y-%m-%d %H:%M}")
    out.append("")

    out.append("## 認識テキスト")
    out.append("")
    for s in rec.segments:
        start = _fmt_time(s.start_ms)
        end = _fmt_time(s.end_ms)
        out.append(f"> [{start}–{end}] (conf={s.confidence:.2f}) {s.text}")
    out.append("")

    out.append("## 音響層 (ESAS)")
    out.append("")
    out.append(f"- **冒頭シグネチャ**: {ac.get('opening_signature', '—')}")
    out.append(f"- **終端シグネチャ**: {ac.get('closing_signature', '—')}")
    out.append("")
    habits = ac.get("habits", [])
    if habits:
        out.append("### 観察された癖")
        out.append("")
        for h in habits:
            seconds = ", ".join(f"{t:.1f}s" for t in h.get("evidence_seconds", []))
            params = ", ".join(h.get("evidence_params", []))
            out.append(f"- **{h.get('name', '?')}** ({seconds} | {params})")
            out.append(f"  - {h.get('description', '')}")
        out.append("")

    out.append("## テキスト層")
    out.append("")
    fillers = tx.get("fillers", [])
    if fillers:
        f_str = "、".join(f'"{f["word"]}" ({f["count"]}回)' for f in fillers)
        out.append(f"- **フィラー**: {f_str}")
    else:
        out.append("- **フィラー**: 検出されず")

    cp = tx.get("conclusion_position", {})
    if cp:
        out.append(
            f"- **結論位置**: {cp.get('zone', '?')} "
            f"(約{cp.get('evidence_second', 0):.1f}s)"
        )
        if cp.get("main_claim"):
            out.append(f"  - 主張: 「{cp['main_claim']}」")

    rt = tx.get("repeated_terms", [])
    if rt:
        rt_str = "、".join(f'"{r["word"]}" ({r["count"]}回)' for r in rt)
        out.append(f"- **繰り返し語**: {rt_str}")

    out.append(f"- **文構造**: {tx.get('sentence_pattern', '—')}")
    out.append(f"- **冒頭フック**: {tx.get('opening_hook', '—')}")
    out.append(f"- **終端ランディング**: {tx.get('closing_landing', '—')}")
    out.append("")

    out.append("## クロス層 ⭐")
    out.append("")
    for i, p in enumerate(cr.get("patterns", []), 1):
        e = p.get("evidence", {})
        out.append(f"### {i}. {p.get('name', '?')}")
        out.append("")
        out.append(
            f"- **証拠**: {e.get('second', 0):.1f}s, "
            f"`{e.get('esas_param', '?')}={e.get('esas_value', '?')}`, "
            f"「{e.get('text_quote', '')}」"
        )
        out.append(f"- **意味**: {p.get('significance', '')}")
        out.append("")

    out.append("## 改善提案")
    out.append("")
    for i, imp in enumerate(cr.get("improvements", []), 1):
        grounded = ", ".join(imp.get("grounded_in", []))
        out.append(f"{i}. {imp.get('suggestion', '')}")
        if grounded:
            out.append(f"   - 根拠: {grounded}")
    out.append("")

    out.append("## ESAS パラメータ統計（参考）")
    out.append("")
    out.append("| パラメータ | 平均 | ピーク値 | ピーク時刻 |")
    out.append("|---|---:|---:|---:|")
    for p in ESAS_PARAMS:
        mean = esas.mean(p)
        peak = esas.peak(p)
        if peak:
            peak_time = peak[0] / 1000
            peak_val = peak[1]
            out.append(f"| `{p}` | {mean:.1f} | {peak_val} | {peak_time:.1f}s |")
        else:
            out.append(f"| `{p}` | — | — | — |")
    out.append("")

    return "\n".join(out)


def _fmt_time(ms: int) -> str:
    s = int(ms // 1000)
    return f"{s // 60:02d}:{s % 60:02d}"
