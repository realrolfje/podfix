# Configuration

Podfix reads TOML configuration files. You can keep everything in one file or split shared and machine-specific settings across multiple files with `include`.

## Minimal Example

```toml
base_url = "https://podfix.example.com"
output_dir = "./output"
keep_original_downloads = false
cache_artwork = false
badge_artwork = false
max_episodes = 20
podcast_mode = "auto"
media_path_token = "media-change-me"

[http]
basic_auth_username = "podfix"
basic_auth_password = "change-me"

[[podcasts]]
slug = "example-news"
upstream_feed_url = "https://example.com/podcast/feed.xml"

[[podcasts]]
slug = "example-series"
upstream_feed_url = "https://example.com/series/feed.xml"
podcast_mode = "story"
max_episodes = "unlimited"
```

## Split Config Example

Shared config:

```toml
# config.shared.toml
keep_original_downloads = false
badge_artwork = true
max_episodes = 5
podcast_mode = "auto"

[[podcasts]]
slug = "example-news"
upstream_feed_url = "https://example.com/podcast/feed.xml"

[ffmpeg]
binary = "ffmpeg"
```

Machine-specific config:

```toml
# config.local.toml or config.server.toml
include = "config.shared.toml"

base_url = "https://podfix.example.com"
output_dir = "./output"
media_path_token = "media-change-me"

[http]
basic_auth_username = "podfix"
basic_auth_password = "change-me"
```

## Merge Rules

- Included files are loaded first.
- The current file overrides scalar values and tables from included files.
- `[[podcasts]]` entries from included files are preserved and appended to any local `[[podcasts]]` entries.
- `include` can be a single string or a list of strings.
- Include paths are resolved relative to the file that declares them.

## Top-Level Settings

### `base_url`

Public base URL where generated podcast pages, feeds, artwork, and episode files will be served.

### `output_dir`

Root directory used for generated data. Podfix writes to `output_dir/data/`, with generated feeds, pages, artwork, and published media under `output_dir/data/published/`.

### `include`

Optional string or list of strings naming TOML files to merge before the current file.

### `keep_original_downloads`

If `true`, keep the original upstream media files under `downloads/<slug>/`. If `false`, only the processed MP3 files are retained publicly.

### `cache_artwork`

If `true`, cache show and episode artwork locally without modification.

### `badge_artwork`

If `true`, cache artwork locally and stamp it with the blue `COMPRESSED` badge. This is independent of `cache_artwork`; enabling either setting causes artwork to be stored locally.

### `max_episodes`

Default number of episodes to retain in each generated feed and show page.

Accepted values:

- Integer: keep a limited window.
- `"unlimited"` or `"all"`: keep all synced episodes.

### `podcast_mode`

Default processing mode for podcasts that do not override it.

Accepted values:

- `news`
- `story`
- `auto`

### `media_path_token`

Secret path segment used for public episode MP3 URLs. This affects both `podfix serve` and static hosting such as nginx.

### `[http]`

HTTP client settings for feed, media, and artwork downloads.

Supported keys:

- `user_agent`
- `timeout_seconds`
- `retries`
- `basic_auth_username`
- `basic_auth_password`

`podfix serve` keeps feeds and pages behind HTTP Basic Auth. Episode MP3 URLs are emitted under a tokenized path from the top-level `media_path_token` setting and are served without auth so podcast apps can stream them directly. If you omit these keys, Podfix uses the defaults `podfix` / `change-me` and `media-change-me`, so change them in your real config.

### `[ffmpeg]`

Default audio processing settings applied to all podcasts unless overridden per show.

Supported keys:

- `binary`
- `highpass_hz`
- `lowpass_hz`
- `compressor_threshold_db`
- `compressor_ratio`
- `attack_ms`
- `release_ms`
- `sample_rate_hz`
- `bitrate_kbps`
- `channels`
- `normalize`
- `loudness_target_lufs`
- `true_peak_db`
- `loudness_range_target`

## `[[podcasts]]` Entries

Each `[[podcasts]]` block defines one generated podcast.

### Required Keys

### `upstream_feed_url`

Source RSS feed for that podcast.

### Optional Keys

### `slug`

URL path segment and output folder name. If omitted, Podfix derives one from the feed URL.

### `podcast_mode`

Per-podcast override for the top-level `podcast_mode`.

### `max_episodes`

Per-podcast override for the top-level `max_episodes`.

### `keep_original_downloads`

Per-podcast override for the top-level setting.

### `cache_artwork`

Per-podcast override for the top-level setting.

### `badge_artwork`

Per-podcast override for the top-level setting.

### `episode_title_include`

Optional case-insensitive regular expression applied to episode titles after feed parsing and before episode windowing. This is intended for shared feeds that contain multiple series.

Example:

```toml
[[podcasts]]
slug = "olaf-zit-vast"
upstream_feed_url = "https://podcast.npo.nl/feed/argos-vriend-van-volkert.xml"
podcast_mode = "story"
max_episodes = "unlimited"
episode_title_include = "olaf zit vast"
```

If the expression is invalid, Podfix fails fast while loading the config.

### `ffmpeg = { ... }`

Inline per-podcast override for audio processing. Only the keys you specify are changed; all other values inherit from the top-level `[ffmpeg]` block.

Example:

```toml
[[podcasts]]
slug = "quiet-interviews"
upstream_feed_url = "https://example.com/interviews/feed.xml"
ffmpeg = { compressor_threshold_db = -24, compressor_ratio = "6", loudness_target_lufs = -14 }
```

## Mode Behavior

### `news`

- On each `sync`, process only the single newest upstream episode.
- Generated feeds and show pages are ordered newest to oldest.
- With `max_episodes`, Podfix keeps the newest `N` synced episodes and prunes anything older.

### `story`

- On each `sync`, process only the single oldest not-yet-synced episode.
- Generated feeds and show pages are ordered oldest to newest.
- With `max_episodes`, Podfix works only within the oldest `N` upstream episodes. Newer episodes are ignored until you raise the limit or use `"unlimited"`.

### `auto`

- Uses RSS metadata when available.
- Currently `itunes:type = serial` maps to `story`.
- All other feeds fall back to `news`.

## Audio Tuning Notes

### `compressor_threshold_db`

Lower values compress more of the signal.

### `compressor_ratio`

Higher values compress peaks more aggressively.

### `channels`

- `1`: mono output
- `2`: stereo output

### `normalize`

If `true`, apply `loudnorm` after compression.

### Loudness Target Settings

The `loudness_target_lufs`, `true_peak_db`, and `loudness_range_target` settings control the `loudnorm` target profile.

## Recommended Layout

- Commit `config.shared.toml` plus example machine-specific config files.
- Keep real `config.local.toml` and `config.server.toml` untracked.
- Put portable podcast definitions in the shared file.
- Override only `base_url` and `output_dir` per machine where possible.
