# Speech Sample Credits & Fetch Commands

This directory holds locally-fetched speech samples for developing and testing
speech-habit-lens. **Audio files are gitignored** — each developer fetches their
own copy with the commands below.

Why not bundle the audio? Most clean sources we use are licensed CC BY-ND, where
extracting a 1-minute segment from a 109-minute talk and redistributing it is
ambiguous. Keeping audio out of the repo sidesteps the question entirely.

---

## sample.wav — Richard Stallman (CC BY-ND 4.0)

| Field | Value |
|---|---|
| **Speaker** | Dr. Richard Stallman |
| **Event** | 180th Nexa Wednesday — "Free/Libre Software and freedom in the digital society" |
| **Date** | 2025-02-12 |
| **Venue** | Politecnico di Torino |
| **Original source** | [archive.org/details/180th-nexa-wednesday](https://archive.org/details/180th-nexa-wednesday) |
| **License** | [CC BY-ND 4.0](https://creativecommons.org/licenses/by-nd/4.0/) |
| **Provider** | Nexa Center for Internet & Society |
| **Full duration** | 109 minutes |
| **Extracted segment** | 00:30 – 01:30 (60 seconds) |
| **Output format** | WAV, 16kHz, mono, 16-bit PCM |

### Fetch command

```bash
./tools/fetch_speech.sh \
  "https://archive.org/download/180th-nexa-wednesday/180th-Nexa-Wednesday.mp4" \
  examples/sample.wav \
  30 60
```

Takes ~6 seconds (HTTP Range download, no need to fetch the full 670MB file).

---

## Adding new samples

When adding a new sample to your local `examples/`:

1. Verify the license allows the use case (analysis + local processing)
2. Run `tools/fetch_speech.sh <url> examples/<name>.wav <start> <duration>`
3. Add a new section to this file with the same field structure
4. **Do not commit the audio file itself** (it's gitignored)
5. If license requires attribution, ensure your `examples/CREDITS.md` entry is
   visible to anyone who might consume your analysis output

### License-friendly sources

| Source | License pattern | Notes |
|---|---|---|
| [Internet Archive](https://archive.org/) | Mixed — check each item | Use the `licenseurl` metadata field |
| [Wikimedia Commons](https://commons.wikimedia.org/) | PD / CC BY-SA | Limited engineer talks, strong historical material |
| Podcast RSS feeds | Configured for download | Attribution still required; check each show's reuse policy |
| [TED downloads](https://www.ted.com/talks) | CC BY-NC-ND | OK for personal analysis, NOT for redistribution |
| Creator self-hosted | Varies (often CC) | gnu.org, IETF talks, conference archives |

### Sources to avoid

| Source | Reason |
|---|---|
| **YouTube (general)** | ToS forbids download. CC-licensed videos must use YouTube Studio's official "Download (Creative Commons)" feature first. |
| **Vimeo / streaming platforms** | Similar ToS constraints |
| **Unidentified license** | If you can't find a licenseurl/copyright statement, skip it |
