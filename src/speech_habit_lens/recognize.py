"""AmiVoice non-sync HTTP recognition wrapper.

Submits a WAV file to AmiVoice's async recognition endpoint, polls until
completion, and returns the recognized text + segments + the raw JSON
(downstream modules parse ESAS from the raw response).
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


AMIVOICE_SUBMIT_URL = "https://acp-api-async.amivoice.com/v1/recognitions"
AMIVOICE_RESULT_URL_TMPL = "https://acp-api-async.amivoice.com/v1/recognitions/{session_id}"

DEFAULT_ENGINE = "-a-general"
DEFAULT_POLL_INTERVAL_S = 2.0
DEFAULT_POLL_TIMEOUT_S = 300.0
SUBMIT_RETRY_DELAYS_S = (2.0, 4.0, 8.0)
RATE_LIMIT_BACKOFF_S = 60.0


class AmiVoiceError(Exception):
    """Raised when an AmiVoice job fails or times out."""


@dataclass
class Segment:
    start_ms: int
    end_ms: int
    text: str
    confidence: float


@dataclass
class RecognitionResult:
    text: str
    segments: list[Segment]
    duration_ms: int
    session_id: str
    raw_response: dict[str, Any]


def recognize(
    wav_path: str | Path,
    *,
    esas: bool = True,
    engine: str = DEFAULT_ENGINE,
    api_key: str | None = None,
    poll_interval_s: float = DEFAULT_POLL_INTERVAL_S,
    poll_timeout_s: float = DEFAULT_POLL_TIMEOUT_S,
) -> RecognitionResult:
    """Submit a WAV to AmiVoice, poll until done, return parsed result.

    Args:
        wav_path: Path to WAV file (16kHz/mono/16-bit recommended).
        esas: Enable ESAS sentiment analysis.
        engine: AmiVoice grammar engine identifier.
        api_key: AmiVoice APPKEY. Falls back to AMIVOICE_API_KEY env var.
        poll_interval_s: Seconds between status polls.
        poll_timeout_s: Maximum seconds to wait for completion.

    Returns:
        RecognitionResult with text, segments, and the raw JSON for ESAS parsing.

    Raises:
        AmiVoiceError: On missing API key, missing file, submit failure after
            retries, polling timeout, or remote job failure.
    """
    api_key = api_key or os.getenv("AMIVOICE_API_KEY")
    if not api_key:
        raise AmiVoiceError(
            "AmiVoice API key not provided. Pass api_key= or set AMIVOICE_API_KEY."
        )

    wav_path = Path(wav_path)
    if not wav_path.is_file():
        raise AmiVoiceError(f"WAV file not found: {wav_path}")

    session_id = _submit_job(wav_path, api_key, engine, esas)
    logger.info("Submitted job: session_id=%s", session_id)

    raw = _poll_until_done(session_id, api_key, poll_interval_s, poll_timeout_s)
    return _parse_response(raw, session_id)


def _submit_job(wav_path: Path, api_key: str, engine: str, esas: bool) -> str:
    d_parts = [f"grammarFileNames={engine}"]
    if esas:
        d_parts.append("sentimentAnalysis=True")
    d_value = " ".join(d_parts)

    last_error: Exception | None = None
    for attempt, delay in enumerate((0.0, *SUBMIT_RETRY_DELAYS_S)):
        if delay > 0:
            logger.warning("Submit retry %d after %.1fs backoff", attempt, delay)
            time.sleep(delay)
        try:
            with wav_path.open("rb") as f:
                resp = httpx.post(
                    AMIVOICE_SUBMIT_URL,
                    data={"u": api_key, "d": d_value},
                    files={"a": (wav_path.name, f, "audio/wav")},
                    timeout=60.0,
                )
            resp.raise_for_status()
            body = resp.json()
            session_id = body.get("sessionid")
            if not session_id:
                raise AmiVoiceError(f"No sessionid in submit response: {body}")
            return session_id
        except (httpx.HTTPError, AmiVoiceError) as e:
            last_error = e
            logger.warning("Submit attempt failed: %s", e)
            continue

    raise AmiVoiceError(f"Submit failed after retries: {last_error}")


def _poll_until_done(
    session_id: str,
    api_key: str,
    interval_s: float,
    timeout_s: float,
) -> dict[str, Any]:
    url = AMIVOICE_RESULT_URL_TMPL.format(session_id=session_id)
    headers = {"Authorization": f"Bearer {api_key}"}

    deadline = time.monotonic() + timeout_s
    while time.monotonic() <= deadline:
        resp = httpx.get(url, headers=headers, timeout=30.0)
        if resp.status_code == 429:
            logger.warning("Rate limited (429), backing off %.0fs", RATE_LIMIT_BACKOFF_S)
            time.sleep(RATE_LIMIT_BACKOFF_S)
            continue
        resp.raise_for_status()
        body = resp.json()
        status = body.get("status")
        logger.debug("Poll status=%s", status)

        if status == "completed":
            return body
        if status in ("error", "failed"):
            raise AmiVoiceError(f"Job failed: status={status}, body={body}")

        time.sleep(interval_s)

    raise AmiVoiceError(
        f"Polling timed out after {timeout_s}s (session_id={session_id})"
    )


def _parse_response(raw: dict[str, Any], session_id: str) -> RecognitionResult:
    """Convert AmiVoice JSON to RecognitionResult.

    AmiVoice nests results 3 levels deep: top.segments[].results[0]. Each
    AmiVoice "segment" is one utterance unit (after silence-based segmentation).
    We flatten to one Segment per AmiVoice segment, using the best (first)
    result's starttime/endtime/confidence/text.
    """
    text = raw.get("text", "")
    av_segments = raw.get("segments", [])

    segments: list[Segment] = []
    duration_ms = 0
    for av_seg in av_segments:
        results = av_seg.get("results", [])
        if not results:
            continue
        r = results[0]
        seg = Segment(
            start_ms=int(r.get("starttime", 0)),
            end_ms=int(r.get("endtime", 0)),
            text=r.get("text", ""),
            confidence=float(r.get("confidence", 0.0)),
        )
        segments.append(seg)
        if seg.end_ms > duration_ms:
            duration_ms = seg.end_ms

    return RecognitionResult(
        text=text,
        segments=segments,
        duration_ms=duration_ms,
        session_id=session_id,
        raw_response=raw,
    )


if __name__ == "__main__":
    import json
    import sys

    from dotenv import load_dotenv

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python -m speech_habit_lens.recognize <wav_path> [--dump-raw]")
        sys.exit(1)

    dump_raw = "--dump-raw" in sys.argv
    result = recognize(sys.argv[1])

    print(f"\n=== Transcript ({result.duration_ms / 1000:.1f}s) ===")
    print(result.text)
    print(f"\n=== Segments ({len(result.segments)}) ===")
    for s in result.segments:
        print(
            f"  [{s.start_ms / 1000:5.1f}-{s.end_ms / 1000:5.1f}s] "
            f"conf={s.confidence:.2f}  {s.text}"
        )
    print(f"\n=== Raw response top-level keys ===")
    print(sorted(result.raw_response.keys()))

    if dump_raw:
        print("\n=== Full raw response ===")
        print(json.dumps(result.raw_response, ensure_ascii=False, indent=2))
