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
import time
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

# Per-process debug directory (avoids race conditions in parallel `shl analyze`
# runs). Override with $SHL_DEBUG_DIR.
_PROCESS_TAG = f"{os.getpid()}-{int(time.time())}"
DEFAULT_DEBUG_DIR = Path("/tmp") / f"shl-{_PROCESS_TAG}"

# Allow one automatic retry when JSON parsing fails on a stop_reason=end_turn
# response (the LLM occasionally generates malformed JSON for transcripts
# containing unusual character sequences).
JSON_PARSE_RETRY_COUNT = 1


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
    """Call one layer with automatic JSON-parse retry on end_turn failures.

    Retries are only triggered when stop_reason=end_turn (the model
    voluntarily stopped). max_tokens truncation is not retried since the
    same prompt will likely truncate again.
    """
    system_prompt = (PROMPTS_DIR / f"{layer_name}.md").read_text(encoding="utf-8")
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    user_content = f"以下のデータを分析してください。\n\n```json\n{payload_json}\n```"

    last_error: AnalysisError | None = None
    last_debug_info: dict[str, Any] = {}

    for attempt in range(JSON_PARSE_RETRY_COUNT + 1):
        attempt_label = f"{layer_name}" if attempt == 0 else f"{layer_name}/retry{attempt}"
        logger.info(
            "[%s] calling %s (max_tokens=%d, payload_chars=%d)",
            attempt_label,
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
            attempt_label,
            stop_reason,
            input_tokens,
            output_tokens,
            len(raw_text),
        )

        debug_path = _dump_raw(
            attempt_label.replace("/", "-"),
            raw_text,
            stop_reason,
            input_tokens,
            output_tokens,
        )

        last_debug_info = {
            "stop_reason": stop_reason,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "debug_path": debug_path,
        }

        if stop_reason == "max_tokens":
            logger.warning(
                "[%s] hit max_tokens limit (%d). Output likely truncated.",
                attempt_label,
                MAX_TOKENS_PER_LAYER,
            )

        try:
            return _extract_json(raw_text, layer_name)
        except AnalysisError as e:
            last_error = e
            # Only retry if the model voluntarily stopped (not on truncation).
            if attempt < JSON_PARSE_RETRY_COUNT and stop_reason == "end_turn":
                logger.warning(
                    "[%s] JSON parse failed (%s). Retrying once.",
                    attempt_label,
                    str(e).splitlines()[0] if str(e) else "unknown",
                )
                continue
            break

    assert last_error is not None
    raise AnalysisError(
        f"{last_error}\n\n"
        f"Stop reason: {last_debug_info['stop_reason']}\n"
        f"Tokens: input={last_debug_info['input_tokens']}, "
        f"output={last_debug_info['output_tokens']}\n"
        f"Full raw output: {last_debug_info['debug_path']}"
    ) from last_error


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
    """Tolerate markdown code-fence wrapping and trailing prose Claude adds."""
    text = text.strip()
    if text.startswith("```"):
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1 :].lstrip()
    # raw_decode reads JSON from the start and ignores anything after, so a
    # trailing ``` fence or markdown commentary appended by the model does
    # not break parsing.
    try:
        obj, _ = json.JSONDecoder().raw_decode(text)
        return obj
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
