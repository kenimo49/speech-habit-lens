"""Parse AmiVoice ESAS (Emotion / Sentiment Analysis Service) data.

ESAS lives at `raw_response["sentiment_analysis"]["segments"]` and emits
20 emotion parameters sampled at ~2 second intervals throughout the audio.
This module converts that nested JSON into a flat EsasTimeline structure
that downstream analysis (acoustic_layer prompts, Plotly charts) can consume.

Parameter names confirmed empirically from AmiVoice response on 2026-05-23
(official docs only listed 5 examples). All 20:

  energy, content, upset, aggression, stress, uncertainty, excitement,
  concentration, emo_cog, hesitation, brain_power, embarrassment,
  intensive_thinking, imagination_activity, extreme_emotion, passionate,
  atmosphere, anticipation, dissatisfaction, confidence

Each value is an integer 0-100 (scale confirmed from observation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ESAS_PARAMS: tuple[str, ...] = (
    "energy",
    "content",
    "upset",
    "aggression",
    "stress",
    "uncertainty",
    "excitement",
    "concentration",
    "emo_cog",
    "hesitation",
    "brain_power",
    "embarrassment",
    "intensive_thinking",
    "imagination_activity",
    "extreme_emotion",
    "passionate",
    "atmosphere",
    "anticipation",
    "dissatisfaction",
    "confidence",
)


@dataclass
class EsasSample:
    """One ESAS observation, covering [start_ms, end_ms]."""

    start_ms: int
    end_ms: int
    params: dict[str, int]


@dataclass
class EsasTimeline:
    """All ESAS samples for one recognition, in chronological order."""

    samples: list[EsasSample]
    duration_ms: int

    def mean(self, param: str) -> float:
        """Mean value of one parameter across all samples (0 if empty)."""
        if not self.samples:
            return 0.0
        return sum(s.params.get(param, 0) for s in self.samples) / len(self.samples)

    def peak(self, param: str) -> tuple[int, int] | None:
        """(timestamp_ms, value) of the sample with the highest value, or None."""
        if not self.samples:
            return None
        best = max(self.samples, key=lambda s: s.params.get(param, 0))
        return best.start_ms, best.params.get(param, 0)

    def series(self, param: str) -> list[tuple[int, int]]:
        """[(start_ms, value)] time series for one parameter."""
        return [(s.start_ms, s.params.get(param, 0)) for s in self.samples]


class EsasParseError(Exception):
    """Raised when the ESAS payload is missing or malformed."""


def parse_esas(raw_response: dict[str, Any]) -> EsasTimeline:
    """Extract EsasTimeline from an AmiVoice raw recognition response.

    Args:
        raw_response: The dict returned by recognize() as `result.raw_response`.

    Returns:
        EsasTimeline with all samples. Empty samples list if ESAS was not
        requested or returned no data (very quiet audio).
    """
    sa = raw_response.get("sentiment_analysis")
    if sa is None:
        return EsasTimeline(samples=[], duration_ms=0)
    if not isinstance(sa, dict):
        raise EsasParseError(
            f"sentiment_analysis is {type(sa).__name__}, expected dict"
        )

    av_samples = sa.get("segments", [])
    samples: list[EsasSample] = []
    duration_ms = 0

    for s in av_samples:
        start_ms = int(s.get("starttime", 0))
        end_ms = int(s.get("endtime", 0))
        params = {p: int(s.get(p, 0)) for p in ESAS_PARAMS}
        samples.append(EsasSample(start_ms=start_ms, end_ms=end_ms, params=params))
        if end_ms > duration_ms:
            duration_ms = end_ms

    return EsasTimeline(samples=samples, duration_ms=duration_ms)


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m speech_habit_lens.esas <raw-response.json>")
        sys.exit(1)

    raw = json.load(open(sys.argv[1], encoding="utf-8"))
    timeline = parse_esas(raw)

    print(f"=== ESAS Timeline ({len(timeline.samples)} samples, {timeline.duration_ms / 1000:.1f}s) ===\n")
    print(f"{'param':<22} {'mean':>6}  {'peak@s':>9}")
    print("-" * 42)
    for p in ESAS_PARAMS:
        m = timeline.mean(p)
        peak = timeline.peak(p)
        peak_str = f"{peak[1]}@{peak[0] / 1000:.1f}" if peak else "—"
        print(f"{p:<22} {m:>6.1f}  {peak_str:>9}")
