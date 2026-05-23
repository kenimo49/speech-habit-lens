"""Three-layer LLM analysis: acoustic → text → cross.

Each layer is one Claude call with its own system prompt (loaded from
prompts/) and a structured JSON payload as the user message. The cross
layer receives the JSON outputs of the prior two layers, which is the
core of speech-habit-lens's body × language correlation discovery.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from .esas import ESAS_PARAMS, EsasTimeline
from .recognize import RecognitionResult

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"

DEFAULT_MODEL = "claude-sonnet-4-6"
# Cross layer can be verbose (3-5 patterns × multi-sentence significance).
# Bumped from 2048 after observing truncated JSON output on the first live run.
MAX_TOKENS_PER_LAYER = 4096

# Where to dump raw layer outputs for debugging. Override with $SHL_DEBUG_DIR.
DEFAULT_DEBUG_DIR = Path("/tmp")


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
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    user_content = f"以下のデータを分析してください。\n\n```json\n{payload_json}\n```"

    logger.info(
        "[%s] calling %s (max_tokens=%d, payload_chars=%d)",
        layer_name,
        model,
        MAX_TOKENS_PER_LAYER,
        len(payload_json),
    )

    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS_PER_LAYER,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = "".join(b.text for b in response.content if b.type == "text")
    stop_reason = response.stop_reason
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens

    logger.info(
        "[%s] response: stop=%s, input=%d, output=%d, chars=%d",
        layer_name,
        stop_reason,
        input_tokens,
        output_tokens,
        len(raw_text),
    )

    debug_path = _dump_raw(layer_name, raw_text, stop_reason, input_tokens, output_tokens)

    if stop_reason == "max_tokens":
        logger.warning(
            "[%s] hit max_tokens limit (%d). Output likely truncated. "
            "Consider raising MAX_TOKENS_PER_LAYER or tightening the prompt.",
            layer_name,
            MAX_TOKENS_PER_LAYER,
        )

    try:
        return _extract_json(raw_text, layer_name)
    except AnalysisError as e:
        raise AnalysisError(
            f"{e}\n\n"
            f"Stop reason: {stop_reason}\n"
            f"Tokens: input={input_tokens}, output={output_tokens}\n"
            f"Full raw output: {debug_path}"
        ) from e


def _dump_raw(
    layer_name: str,
    raw_text: str,
    stop_reason: str | None,
    input_tokens: int,
    output_tokens: int,
) -> Path:
    """Persist the raw LLM output to disk for post-hoc debugging.

    Path overridable via $SHL_DEBUG_DIR. Always written (not conditional on
    verbose), since the file is small and the value at debug-time is high.
    """
    debug_dir = Path(os.getenv("SHL_DEBUG_DIR", str(DEFAULT_DEBUG_DIR)))
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_path = debug_dir / f"shl-{layer_name}.txt"
    header = (
        f"# layer: {layer_name}\n"
        f"# stop_reason: {stop_reason}\n"
        f"# input_tokens: {input_tokens}\n"
        f"# output_tokens: {output_tokens}\n"
        f"# ---\n"
    )
    debug_path.write_text(header + raw_text, encoding="utf-8")
    logger.debug("[%s] raw output saved: %s", layer_name, debug_path)
    return debug_path


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
            f"{layer_name} returned unparseable JSON: {e}\n"
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
