# podcast-proxy

`podcast-proxy` is a small self-hosted Python tool that mirrors an upstream podcast feed, transcodes episode media with `ffmpeg`, and publishes a new RSS feed that points at the processed MP3 files.

Current behavior:

- Fetches and parses an upstream RSS feed
- Keeps local state so unchanged episodes are skipped on normal sync runs
- Downloads audio or video enclosures
- Transcodes everything to MP3 with spoken-word defaults, compression, and optional loudness normalization
- Regenerates a podcast RSS feed under a static `public/` directory
- Can cache and badge artwork locally with a blue `COMPRESSED` pill
- Preserves show artwork and per-episode artwork in the generated feed
- Provides `sync`, `rebuild`, and `serve` CLI commands

## Layout

The generated output tree looks like this:

```text
output/
  data/
    state.json
    cache/
    public/
      feed.xml
      episodes/
      images/
```

Only published MP3s are retained under `public/episodes/`. Temporary download/transcode artifacts are cleaned up after successful processing.

Serve `output/data/public/` with any static web server, or use the built-in convenience command.

## Requirements

- Python 3.11+
- `ffmpeg` available on `PATH`, or point `ffmpeg.binary` at it in config

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

After `pip install -e .`, `pip` creates a console command named `podcast-proxy` from the entrypoint declared in [pyproject.toml](/Users/rolf/temp/podfix/pyproject.toml). That command is installed into your Python environment, not as a file in the project root.

You can inspect where the command lives with:

```bash
which podcast-proxy
```

If you do not want to rely on the installed console script, you can run the CLI directly from the repo:

```bash
PYTHONPATH=src python3 -m podcast_proxy.cli sync --config config.toml
```

## Configuration

Copy [config.sample.toml](/Users/rolf/temp/podfix/config.sample.toml) to `config.toml` and adjust:

```toml
upstream_feed_url = "https://example.com/podcast/feed.xml"
base_url = "https://podcast-proxy.example.com"
output_dir = "./output"
cache_artwork = false
badge_artwork = false
max_episodes = 20
podcast_mode = "auto"
```

Important config values:

- `upstream_feed_url`: source podcast feed
- `base_url`: public base URL where `feed.xml` and `episodes/*.mp3` will be served
- `output_dir`: root for generated data
- `cache_artwork`: if `true`, artwork is cached locally without modification
- `badge_artwork`: if `true`, artwork is cached locally and stamped with a blue `COMPRESSED` badge
- `max_episodes`: only process `N` episodes from the selected window
- `podcast_mode`: `news`, `story`, or `auto`

Mode behavior:

- `news`: treat the newest episodes as relevant and process the latest `N`
- `story`: treat the feed like a documentary or serialized show and process the oldest `N`
- `auto`: use RSS metadata when available; currently `itunes:type = serial` maps to `story`, otherwise it falls back to `news`

Audio tuning:

- `compressor_threshold_db`: lower values compress more of the signal
- `compressor_ratio`: higher values compress peaks harder
- `channels = 1`: mono output
- `channels = 2`: stereo output
- `normalize = true`: adds `loudnorm` after compression
- `loudness_target_lufs`, `true_peak_db`, `loudness_range_target`: loudness normalization targets

## Usage

Sync new items:

```bash
podcast-proxy sync --config config.toml
```

Force a clean rebuild:

```bash
podcast-proxy rebuild --config config.toml
```

`rebuild` force-overwrites existing public episode files and re-runs `ffmpeg`, so updated audio settings take effect even when filenames stay the same.

Serve the generated feed locally:

```bash
podcast-proxy serve --config config.toml --port 8080
```

Then point your podcast app at:

```text
http://localhost:8080/feed.xml
```

## ffmpeg commands

Audio input:

```bash
ffmpeg -y -i INPUT_AUDIO \
  -af "highpass=f=300,lowpass=f=3400,acompressor=threshold=THRESHOLDdB:ratio=RATIO:attack=ATTACK:release=RELEASE,loudnorm=I=TARGET_LUFS:TP=TRUE_PEAK:LRA=LOUDNESS_RANGE" \
  -ar 22050 \
  -ac CHANNELS \
  -b:a BITRATE \
  -codec:a libmp3lame \
  OUTPUT.mp3
```

Video input:

```bash
ffmpeg -y -i INPUT_VIDEO \
  -vn \
  -af "highpass=f=300,lowpass=f=3400,acompressor=threshold=THRESHOLDdB:ratio=RATIO:attack=ATTACK:release=RELEASE,loudnorm=I=TARGET_LUFS:TP=TRUE_PEAK:LRA=LOUDNESS_RANGE" \
  -ar 22050 \
  -ac CHANNELS \
  -b:a BITRATE \
  -codec:a libmp3lame \
  OUTPUT.mp3
```

The actual values come from the `[ffmpeg]` config section in your config file.

Normalization notes:

- `normalize = true` enables a final `loudnorm` stage after compression
- `loudness_target_lufs = -16` is a reasonable spoken-word default
- `true_peak_db = -1.5` keeps peaks under control for MP3 output

## Notes

- `sync` skips unchanged episodes based on stored source metadata.
- `rebuild` always re-fetches the selected episode window and re-encodes the output MP3s.
- Failed episode downloads or transcodes are logged and skipped.
- The state file is written atomically to avoid partial corruption.
- Episode artwork can be reused from the upstream feed or cached locally with a badge, depending on config.
- This tool is intended for personal use and a single feed.
