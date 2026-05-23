"""Three-layer LLM analysis: acoustic → text → cross.

Each layer is one Claude call with its own system prompt (loaded from
prompts/) and a structured JSON payload as the user message. The cross
layer receives the JSON outputs of the prior two layers, which is the
core of speech-habit-lens's body × language correlation discovery.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from .esas import ESAS_PARAMS, EsasTimeline
from .recognize import RecognitionResult

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS_PER_LAYER = 2048


class AnalysisError(Exception):
    """Raised when a layer returns unparseable JSON or the API fails."""


@dataclass
class Analysis:
    acoustic: dict[str, Any]
    text: dict[str, Any]
    cross: dict[str, Any]
    recognition: RecognitionResult
    esas: EsasTimeline
    model: str


def analyze(
    rec: RecognitionResult,
    esas: EsasTimeline,
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
) -> Analysis:
    """Run all three layers sequentially.

    The cross layer is called last with the acoustic/text outputs as input,
    so this is sequential by design (not parallelizable).
    """
    client = Anthropic(api_key=api_key) if api_key else Anthropic()

    acoustic = _call_layer(client, model, "acoustic_layer", _build_acoustic_payload(esas))
    text = _call_layer(client, model, "text_layer", _build_text_payload(rec))
    cross = _call_layer(
        client, model, "cross_layer", _build_cross_payload(rec, esas, acoustic, text)
    )

    return Analysis(
        acoustic=acoustic,
        text=text,
        cross=cross,
        recognition=rec,
        esas=esas,
        model=model,
    )


def _call_layer(
    client: Anthropic,
    model: str,
    layer_name: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    system_prompt = (PROMPTS_DIR / f"{layer_name}.md").read_text(encoding="utf-8")
    user_content = (
        "以下のデータを分析してください。\n\n"
        f"```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    )

    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS_PER_LAYER,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = "".join(b.text for b in response.content if b.type == "text")
    return _extract_json(raw_text, layer_name)


def _extract_json(text: str, layer_name: str) -> dict[str, Any]:
    """Tolerate markdown code-fence wrapping that Claude sometimes adds."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AnalysisError(
            f"{layer_name} returned unparseable JSON: {e}\n\n"
            f"Raw output (first 500 chars):\n{text[:500]}"
        ) from e


def _build_acoustic_payload(esas: EsasTimeline) -> dict[str, Any]:
    return {
        "duration_ms": esas.duration_ms,
        "samples": [
            {"start_ms": s.start_ms, "end_ms": s.end_ms, **s.params}
            for s in esas.samples
        ],
    }


def _build_text_payload(rec: RecognitionResult) -> dict[str, Any]:
    return {
        "text": rec.text,
        "duration_seconds": round(rec.duration_ms / 1000, 2),
        "segments": [
            {
                "start_s": round(s.start_ms / 1000, 2),
                "end_s": round(s.end_ms / 1000, 2),
                "text": s.text,
                "confidence": s.confidence,
            }
            for s in rec.segments
        ],
    }


def _build_cross_payload(
    rec: RecognitionResult,
    esas: EsasTimeline,
    acoustic: dict[str, Any],
    text: dict[str, Any],
) -> dict[str, Any]:
    return {
        "acoustic": acoustic,
        "text": text,
        "duration_seconds": round(rec.duration_ms / 1000, 2),
        "transcript_segments": [
            {
                "start_s": round(s.start_ms / 1000, 2),
                "end_s": round(s.end_ms / 1000, 2),
                "text": s.text,
            }
            for s in rec.segments
        ],
        "esas_samples": [
            {"start_s": round(s.start_ms / 1000, 2), **{p: s.params[p] for p in ESAS_PARAMS}}
            for s in esas.samples
        ],
    }
