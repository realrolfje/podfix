from __future__ import annotations

from dataclasses import asdict
import logging
from pathlib import Path
from typing import Any

from .artwork import process_artwork
from .config import AppConfig, PodcastConfig
from .feed import Episode, cache_artwork, fetch_feed, make_session
from .media import download_media, transcode_media_with_options
from .rss import write_feed, write_library_index, write_podcast_index
from .state import StateStore


LOGGER = logging.getLogger(__name__)


def sync(config: AppConfig, rebuild: bool = False) -> Path:
    _cleanup_legacy_root_public(config)
    summaries: list[dict[str, Any]] = []
    for podcast in config.podcasts:
        summaries.append(_sync_podcast(podcast, rebuild=rebuild))
    write_library_index(config, summaries)
    return config.public_index


def _sync_podcast(config: PodcastConfig, rebuild: bool) -> dict[str, Any]:
    state_store = StateStore(config.state_file)
    state = state_store.load()
    if rebuild:
        state = {"episodes": {}, "feed": {}}

    session = make_session(config)
    snapshot = fetch_feed(session, config, state)
    if snapshot.not_modified:
        LOGGER.info("feed not modified for %s; regenerating from saved state", config.slug)
        metadata = _normalize_metadata_urls(config, state.get("feed", {}).get("metadata", {}))
        episode_records = [
            _normalize_record_urls(config, record)
            for record in state.get("episodes", {}).values()
        ]
        write_feed(config, metadata, episode_records)
        write_podcast_index(config, metadata, episode_records)
        return _podcast_summary(config, metadata, episode_records)

    metadata = dict(snapshot.metadata)
    if metadata.get("image_url") and (config.cache_artwork or config.badge_artwork):
        try:
            if config.badge_artwork:
                metadata["image_url"] = process_artwork(
                    session, config, metadata["image_url"]
                )
            else:
                cached_url, _ = cache_artwork(session, config, metadata["image_url"])
                metadata["image_url"] = cached_url
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("artwork cache failed for %s: %s", config.slug, exc)

    episode_state = dict(state.get("episodes", {}))
    next_episode_state: dict[str, dict[str, Any]] = {}

    for episode in snapshot.episodes:
        previous = episode_state.get(episode.guid)
        signature = _episode_signature(episode)
        if previous and previous.get("signature") == signature and not rebuild:
            LOGGER.info("skip existing episode for %s: %s", config.slug, episode.title)
            _ensure_public_copy(config, previous)
            next_episode_state[episode.guid] = previous
            continue
        try:
            LOGGER.info("processing %s: %s", config.slug, episode.title)
            image_url = episode.image_url
            if image_url and config.badge_artwork:
                image_url = process_artwork(session, config, image_url)
            source_path = download_media(session, config, episode)
            public_path = transcode_media_with_options(
                config,
                source_path,
                episode,
                force=rebuild,
            )
            public_name = public_path.name
            next_episode_state[episode.guid] = {
                **asdict(episode),
                "image_url": image_url,
                "signature": signature,
                "processed_file": public_name,
                "enclosure_url": f"{config.public_base_url}/episodes/{public_name}",
                "enclosure_length": public_path.stat().st_size,
                "enclosure_type": "audio/mpeg",
            }
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("episode failed for %s: %s (%s)", config.slug, episode.title, exc)
            if previous:
                next_episode_state[episode.guid] = previous

    ordered_records = _ordered_records(snapshot.episodes, next_episode_state)
    ordered_records = [_normalize_record_urls(config, record) for record in ordered_records]
    metadata = _normalize_metadata_urls(config, metadata)
    write_feed(config, metadata, ordered_records)
    write_podcast_index(config, metadata, ordered_records)

    next_state = {
        "feed": {
            "etag": snapshot.etag,
            "last_modified": snapshot.last_modified,
            "metadata": metadata,
        },
        "episodes": next_episode_state,
    }
    state_store.save(next_state)
    return _podcast_summary(config, metadata, ordered_records)


def _podcast_summary(
    config: PodcastConfig,
    metadata: dict[str, Any],
    episode_records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "slug": config.slug,
        "title": metadata.get("title", config.slug),
        "description": metadata.get("description", ""),
        "image_url": metadata.get("image_url"),
        "feed_url": config.feed_url,
        "index_url": config.index_url,
        "episode_count": len(episode_records),
    }


def _normalize_metadata_urls(
    config: PodcastConfig,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(metadata)
    if normalized.get("image_url"):
        normalized["image_url"] = _normalize_local_artwork_url(
            config, normalized["image_url"]
        )
    return normalized


def _normalize_record_urls(
    config: PodcastConfig,
    record: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(record)
    if normalized.get("image_url"):
        normalized["image_url"] = _normalize_local_artwork_url(
            config, normalized["image_url"]
        )
    if normalized.get("enclosure_url"):
        normalized["enclosure_url"] = _normalize_local_episode_url(
            config, normalized["enclosure_url"]
        )
    return normalized


def _normalize_local_artwork_url(config: PodcastConfig, url: str) -> str:
    legacy_prefix = f"{config.base_url}/images/"
    if str(url).startswith(legacy_prefix):
        return f"{config.public_base_url}/images/{str(url)[len(legacy_prefix):]}"
    return str(url)


def _normalize_local_episode_url(config: PodcastConfig, url: str) -> str:
    legacy_prefix = f"{config.base_url}/episodes/"
    if str(url).startswith(legacy_prefix):
        return f"{config.public_base_url}/episodes/{str(url)[len(legacy_prefix):]}"
    return str(url)


def _ensure_public_copy(config: PodcastConfig, record: dict[str, Any]) -> None:
    processed_name = record.get("processed_file")
    if not processed_name:
        return
    public_path = config.public_episodes_dir / processed_name
    if not public_path.exists():
        LOGGER.warning("expected public episode is missing: %s", public_path.name)


def _episode_signature(episode: Episode) -> str:
    return "|".join(
        [episode.enclosure_url, episode.enclosure_type, episode.published, episode.title]
    )


def _ordered_records(
    episodes: list[Episode],
    episode_state: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for episode in episodes:
        record = episode_state.get(episode.guid)
        if record:
            records.append(record)
    return records


def _cleanup_legacy_root_public(config: AppConfig) -> None:
    if any(podcast.legacy_root for podcast in config.podcasts):
        return
    for name in ("feed.xml", "episodes", "images"):
        path = config.public_dir / name
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            for child in sorted(path.rglob("*"), reverse=True):
                if child.is_file():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            path.rmdir()
