Build a small self-hosted podcast proxy in Python.

Goal:
- Input is an upstream podcast RSS feed URL.
- The tool fetches the upstream feed, downloads episodes, post-processes the media with ffmpeg, and publishes a new RSS feed that points to the processed media files.
- The output should be suitable for personal use in a podcast app.

Functional requirements:
1. Feed handling
- Fetch and parse an upstream RSS podcast feed.
- Preserve normal podcast metadata as much as possible:
  - channel title
  - description / subtitle / summary
  - author if present
  - language
  - category
  - explicit flag
  - artwork / image URLs
  - episode title
  - episode description / content
  - pubDate
  - GUID
- For non-audio assets such as cover art, do not re-encode them. Either:
  - hotlink to the original source URL, or
  - optionally cache them locally while preserving original content type.
- Keep a local state file so already processed episodes are not re-downloaded or reprocessed.

2. Media handling
- For each episode enclosure:
  - detect whether the source is audio or video.
  - if it is audio, download and process the audio.
  - if it is video, extract only the audio stream and process that.
- Use ffmpeg for all media processing.
- Processing chain:
  - band-pass style filtering using highpass + lowpass
  - dynamic range compression
  - resampling
  - output MP3
- Make the ffmpeg settings configurable, with sensible defaults for spoken-word podcasts.

Default ffmpeg settings:
- highpass: 300 Hz
- lowpass: 3400 Hz
- compressor threshold: -18 dB
- compressor ratio: 3:1
- attack: 20 ms
- release: 250 ms
- sample rate: 22050 Hz
- output bitrate: 64k mono or stereo depending on config

3. RSS output
- Generate a valid RSS podcast feed from the processed episodes.
- The new feed must:
  - point enclosure URLs to the processed local files
  - set enclosure length to the processed file byte size
  - set enclosure type correctly, usually audio/mpeg
  - preserve episode metadata as much as possible
  - preserve or map GUIDs consistently
- The generated feed should include top-level podcast image/artwork.
- For episodes originating from video, still publish them as audio podcast episodes in the output feed.

4. Hosting layout
- Produce a local output directory structure like:
  - data/
    - state.json
    - downloads/
    - processed/
    - cache/
    - public/
      - feed.xml
      - episodes/
      - images/
- The generated feed.xml should reference files under public/.
- Make it easy to serve public/ with a simple static web server.

5. Incremental sync
- On each run:
  - fetch the upstream feed
  - detect new episodes
  - process only new or changed episodes
  - regenerate the output RSS feed
- Do not reprocess existing episodes unless forced.
- Add a command line flag like --rebuild to regenerate everything.

6. Error handling
- If an episode download fails, skip it and continue.
- If ffmpeg fails for one episode, report it and continue.
- Never corrupt the state file on partial failure.
- Log clearly what happened per episode.

7. Configuration
- Use a config file in YAML or TOML.
- Config should include:
  - upstream feed URL
  - site/base URL for generated enclosure links
  - output directory
  - ffmpeg binary path
  - filter/compression/resample settings
  - whether to cache artwork locally or keep original URLs
  - max number of episodes to process
  - user agent for HTTP requests
  - timeout and retry settings

8. Technical preferences
- Use Python 3.
- Prefer well-known libraries:
  - requests or httpx
  - feedparser if useful
  - lxml or xml.etree for RSS generation
  - pathlib
  - subprocess for ffmpeg
- Keep the code simple and maintainable.
- Split into modules:
  - config
  - feed fetch/parse
  - media download
  - transcoding
  - rss generation
  - state management
  - CLI entrypoint
- Add type hints.
- Add a README with setup and usage instructions.

9. CLI
- Provide a command line interface such as:
  - podcast-proxy sync --config config.toml
  - podcast-proxy rebuild --config config.toml
  - podcast-proxy serve --config config.toml --port 8080
- serve can use Python’s built-in static server for public/ as a convenience.

10. Nice extras if easy
- Sanitize filenames safely.
- Preserve episode ordering by pubDate.
- Optionally limit to the most recent N episodes.
- Optionally store the original enclosure URL in episode metadata.
- Optionally support ETag / Last-Modified for feed fetching and media fetching.

Important implementation details:
- Some upstream podcast episodes may be MP3, M4A, AAC, or MP4 video.
- For video inputs, extract audio only with ffmpeg and ignore the video stream.
- All output episodes should be MP3.
- Cover art and similar assets should still be available from the output feed, either by local caching or by referencing the original source.
- Assume this is for personal use. Do not add DRM, authentication, or multi-user features.

Please:
1. Propose the project structure.
2. Create the initial implementation.
3. Add a sample config file.
4. Add a README.
5. Show the exact ffmpeg commands used for audio and video inputs.
6. Keep the first version minimal but working.