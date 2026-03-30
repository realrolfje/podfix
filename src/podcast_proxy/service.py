from __future__ import annotations

from dataclasses import asdict
from email.utils import parsedate_to_datetime
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
    summaries.sort(key=lambda item: str(item.get("title", "")).casefold())
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
        LOGGER.info(
            "feed not modified for %s; checking current feed for backlog progress",
            config.slug,
        )
        snapshot = fetch_feed(
            session,
            config,
            state,
            use_conditional_headers=False,
        )
        if snapshot.not_modified:
            metadata = _normalize_metadata_urls(
                config, state.get("feed", {}).get("metadata", {})
            )
            episode_records = _renderable_records(
                state.get("episodes", {}).values(),
                _resolved_mode(metadata),
                config.max_episodes,
            )
            episode_records = [
                _normalize_record_urls(config, record) for record in episode_records
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
    next_episode_state: dict[str, dict[str, Any]] = dict(episode_state)
    episodes_to_process = _episodes_to_process(
        snapshot.episodes,
        episode_state,
        snapshot.resolved_mode,
        config.max_episodes,
        rebuild,
    )

    for episode in episodes_to_process:
        previous = episode_state.get(episode.guid)
        signature = _episode_signature(episode)
        if previous and _record_matches_episode(previous, episode) and not rebuild:
            LOGGER.info("skip existing episode for %s: %s", config.slug, episode.title)
            _ensure_public_copy(config, previous)
            next_episode_state[episode.guid] = {
                **previous,
                "signature": signature,
                "source_signature": _source_signature(episode),
            }
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
                "source_signature": _source_signature(episode),
                "processed_file": public_name,
                "enclosure_url": f"{config.public_base_url}/episodes/{public_name}",
                "enclosure_length": public_path.stat().st_size,
                "enclosure_type": "audio/mpeg",
            }
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("episode failed for %s: %s (%s)", config.slug, episode.title, exc)
            if previous:
                next_episode_state[episode.guid] = previous

    next_episode_state = _prune_episode_state(
        snapshot.episodes,
        next_episode_state,
        snapshot.resolved_mode,
        config.max_episodes,
    )
    ordered_records = _ordered_records(
        snapshot.episodes,
        next_episode_state,
        snapshot.resolved_mode,
        config.max_episodes,
    )
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
        [episode.guid, episode.enclosure_type, episode.published, episode.title]
    )


def _source_signature(episode: Episode) -> str:
    return "|".join(
        [episode.enclosure_url, episode.enclosure_type, episode.published, episode.title]
    )


def _record_matches_episode(record: dict[str, Any], episode: Episode) -> bool:
    current_signature = _episode_signature(episode)
    source_signature = _source_signature(episode)
    stored_signature = record.get("signature")
    stored_source_signature = record.get("source_signature")
    return (
        stored_signature == current_signature
        or stored_signature == source_signature
        or stored_source_signature == source_signature
    )


def _episodes_to_process(
    episodes: list[Episode],
    episode_state: dict[str, dict[str, Any]],
    resolved_mode: str,
    max_episodes: int | None,
    rebuild: bool,
) -> list[Episode]:
    if rebuild:
        return _eligible_feed_window(episodes, resolved_mode, max_episodes)
    if not episodes:
        return []
    if resolved_mode == "news":
        return [episodes[0]]
    for episode in _eligible_feed_window(episodes, resolved_mode, max_episodes):
        previous = episode_state.get(episode.guid)
        if not previous or not _record_matches_episode(previous, episode):
            return [episode]
    return []


def _eligible_feed_window(
    episodes: list[Episode],
    resolved_mode: str,
    max_episodes: int | None,
) -> list[Episode]:
    if resolved_mode == "story" and max_episodes is not None:
        return episodes[:max_episodes]
    if resolved_mode == "news" and max_episodes is not None:
        return episodes[:max_episodes]
    return episodes


def _ordered_records(
    episodes: list[Episode],
    episode_state: dict[str, dict[str, Any]],
    resolved_mode: str,
    max_episodes: int | None,
) -> list[dict[str, Any]]:
    eligible_guids = {
        episode.guid for episode in _eligible_feed_window(episodes, resolved_mode, max_episodes)
    }
    records: list[dict[str, Any]] = []
    for episode in _sort_episodes(episodes, resolved_mode):
        if eligible_guids and episode.guid not in eligible_guids:
            continue
        record = episode_state.get(episode.guid)
        if record:
            records.append(record)
    return records


def _prune_episode_state(
    episodes: list[Episode],
    episode_state: dict[str, dict[str, Any]],
    resolved_mode: str,
    max_episodes: int | None,
) -> dict[str, dict[str, Any]]:
    if max_episodes is None:
        return episode_state
    eligible_guids = {
        episode.guid for episode in _eligible_feed_window(episodes, resolved_mode, max_episodes)
    }
    return {
        guid: record
        for guid, record in episode_state.items()
        if guid in eligible_guids
    }


def _renderable_records(
    records: Any,
    resolved_mode: str,
    max_episodes: int | None,
) -> list[dict[str, Any]]:
    ordered = sorted(
        (dict(record) for record in records),
        key=_record_sort_key,
        reverse=(resolved_mode == "news"),
    )
    if max_episodes is not None:
        return ordered[:max_episodes]
    return ordered


def _record_sort_key(record: dict[str, Any]) -> tuple[int, str]:
    published = str(record.get("published", ""))
    if not published:
        return (0, str(record.get("guid", "")))
    try:
        return (1, parsedate_to_datetime(published).isoformat())
    except (TypeError, ValueError, IndexError):
        return (0, published)


def _sort_episodes(episodes: list[Episode], resolved_mode: str) -> list[Episode]:
    return sorted(
        episodes,
        key=lambda episode: _record_sort_key(
            {"published": episode.published, "guid": episode.guid}
        ),
        reverse=(resolved_mode == "news"),
    )


def _resolved_mode(metadata: dict[str, Any]) -> str:
    mode = str(metadata.get("resolved_mode") or "").strip().lower()
    if mode in {"news", "story"}:
        return mode
    itunes_type = str(metadata.get("itunes_type") or "").strip().lower()
    if itunes_type == "serial":
        return "story"
    return "news"


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
