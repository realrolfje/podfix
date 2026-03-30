from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import feedparser
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import PodcastConfig
from .utils import sanitize_filename, sha1_text


@dataclass(slots=True)
class Episode:
    guid: str
    title: str
    description: str
    published: str
    enclosure_url: str
    enclosure_type: str
    source_kind: str
    slug: str
    author: str | None
    original_link: str | None
    image_url: str | None


@dataclass(slots=True)
class FeedSnapshot:
    metadata: dict[str, Any]
    episodes: list[Episode]
    etag: str | None
    last_modified: str | None
    not_modified: bool = False
    resolved_mode: str = "news"


def make_session(config: PodcastConfig) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": config.http.user_agent})
    retry = Retry(
        total=config.http.retries,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def fetch_feed(
    session: requests.Session,
    config: PodcastConfig,
    previous_state: dict[str, Any],
) -> FeedSnapshot:
    headers: dict[str, str] = {}
    feed_state = previous_state.get("feed", {})
    if feed_state.get("etag"):
        headers["If-None-Match"] = feed_state["etag"]
    if feed_state.get("last_modified"):
        headers["If-Modified-Since"] = feed_state["last_modified"]

    response = session.get(
        config.upstream_feed_url,
        headers=headers,
        timeout=config.http.timeout_seconds,
    )
    if response.status_code == 304:
        return FeedSnapshot(
            metadata=feed_state.get("metadata", {}),
            episodes=[],
            etag=feed_state.get("etag"),
            last_modified=feed_state.get("last_modified"),
            not_modified=True,
        )
    response.raise_for_status()

    parsed = feedparser.parse(response.content)
    feed = parsed.feed
    entries = list(parsed.entries)
    episodes = [_entry_to_episode(entry) for entry in entries if _has_enclosure(entry)]
    resolved_mode = _resolve_podcast_mode(feed, config.podcast_mode)
    episodes.sort(key=_sort_key, reverse=(resolved_mode == "news"))

    metadata = {
        "title": feed.get("title", "Podcast Proxy"),
        "description": feed.get("subtitle")
        or feed.get("summary")
        or feed.get("description", ""),
        "author": feed.get("author"),
        "language": feed.get("language"),
        "category": _first_category(feed),
        "explicit": _find_explicit(feed),
        "image_url": _find_image(feed),
        "link": feed.get("link"),
        "itunes_type": _find_itunes_type(feed),
        "resolved_mode": resolved_mode,
    }
    return FeedSnapshot(
        metadata=metadata,
        episodes=episodes,
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
        resolved_mode=resolved_mode,
    )


def cache_artwork(
    session: requests.Session,
    config: PodcastConfig,
    image_url: str,
) -> tuple[str, str | None]:
    response = session.get(image_url, timeout=config.http.timeout_seconds)
    response.raise_for_status()
    extension = _extension_for_content_type(
        response.headers.get("Content-Type", "")
    ) or Path(image_url).suffix or ".img"
    filename = f"artwork-{sha1_text(image_url)}{extension}"
    destination = config.public_images_dir / filename
    destination.write_bytes(response.content)
    public_url = f"{config.public_base_url}/images/{filename}"
    return public_url, response.headers.get("Content-Type")


def _entry_to_episode(entry: Any) -> Episode:
    enclosure = entry.enclosures[0]
    guid = (
        entry.get("id")
        or entry.get("guid")
        or enclosure.get("href")
        or entry.get("link")
        or sha1_text(entry.get("title", "episode"))
    )
    enclosure_url = enclosure.get("href", "")
    content_type = enclosure.get("type", "") or ""
    source_kind = "video" if content_type.startswith("video/") else _kind_from_url(
        enclosure_url
    )
    slug_source = f"{entry.get('published', '')}-{entry.get('title', guid)}-{guid}"
    slug = sanitize_filename(slug_source)[:120] or sha1_text(guid)
    return Episode(
        guid=guid,
        title=entry.get("title", "Untitled Episode"),
        description=_episode_description(entry),
        published=entry.get("published", ""),
        enclosure_url=enclosure_url,
        enclosure_type=content_type,
        source_kind=source_kind,
        slug=slug,
        author=entry.get("author"),
        original_link=entry.get("link"),
        image_url=_find_image(entry),
    )


def _episode_description(entry: Any) -> str:
    if entry.get("summary"):
        return entry.summary
    content = entry.get("content")
    if content:
        return content[0].get("value", "")
    return ""


def _has_enclosure(entry: Any) -> bool:
    return bool(entry.get("enclosures"))


def _first_category(feed: Any) -> str | None:
    tags = feed.get("tags") or []
    if not tags:
        return None
    return tags[0].get("term")


def _find_explicit(feed: Any) -> str | None:
    return (
        feed.get("itunes_explicit")
        or feed.get("explicit")
        or feed.get("tags", [{}])[0].get("itunes_explicit")
    )


def _find_image(feed: Any) -> str | None:
    image = feed.get("image") or {}
    if isinstance(image, dict) and image.get("href"):
        return image["href"]
    return feed.get("itunes_image", {}).get("href") or feed.get("logo")


def _find_itunes_type(feed: Any) -> str | None:
    return feed.get("itunes_type")


def _extension_for_content_type(content_type: str) -> str | None:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    return mapping.get(content_type.split(";")[0].strip().lower())


def _kind_from_url(url: str) -> str:
    lower = url.lower()
    if lower.endswith((".mp4", ".m4v", ".mov", ".webm", ".mkv")):
        return "video"
    return "audio"


def _sort_key(episode: Episode) -> tuple[int, str]:
    if not episode.published:
        return (0, episode.guid)
    try:
        return (1, parsedate_to_datetime(episode.published).isoformat())
    except (TypeError, ValueError, IndexError):
        return (0, episode.published)


def _resolve_podcast_mode(feed: Any, configured_mode: str) -> str:
    if configured_mode in {"news", "story"}:
        return configured_mode
    itunes_type = str(_find_itunes_type(feed) or "").strip().lower()
    if itunes_type == "serial":
        return "story"
    return "news"
