#!/usr/bin/env bash
#
# fetch_speech.sh — clean-source speech audio fetcher for speech-habit-lens
#
# Downloads (or reads local file) and converts an audio/video source into a
# 16kHz mono 16-bit WAV file suitable for AmiVoice + speech-habit-lens.
#
# Supported input sources (license-clean):
#   - Internet Archive direct URLs           (archive.org/download/...)
#   - TED official download URLs             (ted.com/talks/.../download)
#   - Podcast RSS enclosure URLs             (any direct MP3/MP4 link)
#   - Creator self-hosted files              (gnu.org, ietf.org, etc.)
#   - Local files                            (.mp3, .mp4, .wav, .ogg, etc.)
#
# NOT supported (by design):
#   - YouTube / Vimeo / streaming platforms whose ToS forbids download.
#     If you have a CC-licensed YouTube video, use YouTube's official
#     "Download (Creative Commons)" feature in Studio first, then point
#     this script at the local file.
#
# Usage:
#   ./tools/fetch_speech.sh <input> <output.wav> [start-seconds] [duration-seconds]
#
# Examples:
#   ./tools/fetch_speech.sh https://archive.org/download/foo/foo.mp4 examples/sample.wav 30 60
#   ./tools/fetch_speech.sh ~/Downloads/talk.mp3 examples/my-talk.wav 0 90

set -euo pipefail

if [ $# -lt 2 ]; then
  sed -n '3,30p' "$0"
  exit 1
fi

INPUT="$1"
OUTPUT="$2"
START="${3:-0}"
DURATION="${4:-60}"

mkdir -p "$(dirname "$OUTPUT")"

echo "→ Source:   $INPUT"
echo "→ Output:   $OUTPUT"
echo "→ Range:    start=${START}s, duration=${DURATION}s"
echo

# -ss before -i = fast seek (skip to start without decoding intermediate frames)
# -t = duration limit
# -vn = drop video stream
# -ac 1 = mono
# -ar 16000 = 16kHz sample rate (AmiVoice general engine optimal)
# -sample_fmt s16 = 16-bit PCM
ffmpeg -y -hide_banner -loglevel warning \
  -ss "$START" -t "$DURATION" \
  -i "$INPUT" \
  -vn \
  -ac 1 \
  -ar 16000 \
  -sample_fmt s16 \
  "$OUTPUT"

echo
echo "→ Done. Verifying output..."
ffprobe -v error \
  -show_entries format=duration,size \
  -show_entries stream=sample_rate,channels,bits_per_sample,codec_name \
  -of default=noprint_wrappers=1 \
  "$OUTPUT"
