from __future__ import annotations

from dataclasses import asdict
import logging
from pathlib import Path
from typing import Any

from .artwork import process_artwork
from .config import Config
from .feed import Episode, cache_artwork, fetch_feed, make_session
from .media import download_media, transcode_media_with_options
from .rss import write_feed
from .state import StateStore


LOGGER = logging.getLogger(__name__)


def sync(config: Config, rebuild: bool = False) -> Path:
    state_store = StateStore(config.state_file)
    state = state_store.load()
    if rebuild:
        state = {"episodes": {}, "feed": {}}

    session = make_session(config)
    snapshot = fetch_feed(session, config, state)
    if snapshot.not_modified:
        LOGGER.info("feed not modified; regenerating RSS from saved state")
        episode_records = list(state.get("episodes", {}).values())
        write_feed(config, state.get("feed", {}).get("metadata", {}), episode_records)
        return config.public_feed

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
            LOGGER.warning("artwork cache failed: %s", exc)

    episode_state = dict(state.get("episodes", {}))
    next_episode_state: dict[str, dict[str, Any]] = {}

    for episode in snapshot.episodes:
        previous = episode_state.get(episode.guid)
        signature = _episode_signature(episode)
        if previous and previous.get("signature") == signature and not rebuild:
            LOGGER.info("skip existing episode: %s", episode.title)
            _ensure_public_copy(config, previous)
            next_episode_state[episode.guid] = previous
            continue
        try:
            LOGGER.info("processing episode: %s", episode.title)
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
                "enclosure_url": f"{config.base_url}/episodes/{public_name}",
                "enclosure_length": public_path.stat().st_size,
                "enclosure_type": "audio/mpeg",
            }
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("episode failed: %s (%s)", episode.title, exc)
            if previous:
                next_episode_state[episode.guid] = previous

    ordered_records = _ordered_records(snapshot.episodes, next_episode_state)
    write_feed(config, metadata, ordered_records)

    next_state = {
        "feed": {
            "etag": snapshot.etag,
            "last_modified": snapshot.last_modified,
            "metadata": metadata,
        },
        "episodes": next_episode_state,
    }
    state_store.save(next_state)
    return config.public_feed


def _ensure_public_copy(config: Config, record: dict[str, Any]) -> None:
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
