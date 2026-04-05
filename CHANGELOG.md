# Changelog

All notable changes to this project will be documented in this file.

## v0.1.0 - 2026-04-05

### Added

- Multi-podcast support from a single TOML config file.
- Generated library and per-show HTML pages for published feeds.
- Copy-to-clipboard RSS flow for easier podcast app setup.
- Artwork caching and optional badging for published artwork.
- `sync`, `refresh`, `rebuild`, and `serve` CLI commands.
- Tokenized public media paths plus HTTP Basic Auth support for private hosting.

### Changed

- Library and show pages now place search in the hero header.
- Published episode URLs are normalized through state-backed public media paths.
- Library and show pages are regenerated consistently from the current state and feed window.

### Fixed

- Missing published MP3 files are repaired or dropped from state on later runs.
- Missing published artwork files are refreshed from feed data or cleared from stale state.
- Empty-state search messages now show correctly when no podcasts or episodes match.
- Show pages no longer expose a confusing `Open RSS` action; only `Copy RSS Link` remains.
