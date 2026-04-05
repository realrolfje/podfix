from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Any

from .utils import sanitize_filename

FeedMode = str
DEFAULT_MEDIA_PATH_TOKEN = "media-change-me"


@dataclass(slots=True)
class HTTPConfig:
    user_agent: str = "podcast-proxy/0.1"
    timeout_seconds: float = 30.0
    retries: int = 2
    basic_auth_username: str = "podfix"
    basic_auth_password: str = "change-me"


@dataclass(slots=True)
class FFMpegConfig:
    binary: str = "ffmpeg"
    highpass_hz: int = 300
    lowpass_hz: int = 3400
    compressor_threshold_db: int = -18
    compressor_ratio: str = "3"
    attack_ms: int = 20
    release_ms: int = 250
    sample_rate_hz: int = 22050
    bitrate_kbps: int = 64
    channels: int = 1
    normalize: bool = True
    loudness_target_lufs: float = -16.0
    true_peak_db: float = -1.5
    loudness_range_target: float = 11.0


@dataclass(slots=True)
class PodcastConfig:
    slug: str
    upstream_feed_url: str
    episode_title_include: str | None
    base_url: str
    output_dir: Path
    keep_original_downloads: bool
    cache_artwork: bool
    badge_artwork: bool
    max_episodes: int | None
    podcast_mode: FeedMode
    media_path_token: str
    http: HTTPConfig
    ffmpeg: FFMpegConfig
    legacy_root: bool = False

    @property
    def data_dir(self) -> Path:
        return self.output_dir / "data"

    @property
    def state_dir(self) -> Path:
        return self.data_dir / "state"

    @property
    def state_file(self) -> Path:
        if self.legacy_root:
            return self.data_dir / "state.json"
        return self.state_dir / f"{self.slug}.json"

    @property
    def downloads_dir(self) -> Path:
        if self.legacy_root:
            return self.data_dir / "downloads"
        return self.data_dir / "downloads" / self.slug

    @property
    def cache_dir(self) -> Path:
        if self.legacy_root:
            return self.data_dir / "cache"
        return self.data_dir / "cache" / self.slug

    @property
    def public_root_dir(self) -> Path:
        return self.data_dir / "public"

    @property
    def public_dir(self) -> Path:
        if self.legacy_root:
            return self.public_root_dir
        return self.public_root_dir / self.slug

    @property
    def public_feed(self) -> Path:
        return self.public_dir / "feed.xml"

    @property
    def public_index(self) -> Path:
        return self.public_dir / "index.html"

    @property
    def public_media_root_dir(self) -> Path:
        return self.public_root_dir / self.media_path_token

    @property
    def public_episodes_dir(self) -> Path:
        if self.legacy_root:
            return self.public_media_root_dir / "episodes"
        return self.public_media_root_dir / self.slug / "episodes"

    @property
    def legacy_public_episodes_dir(self) -> Path:
        return self.public_dir / "episodes"

    @property
    def public_images_dir(self) -> Path:
        return self.public_dir / "images"

    @property
    def public_base_url(self) -> str:
        if self.legacy_root:
            return self.base_url
        return f"{self.base_url}/{self.slug}"

    @property
    def public_media_base_url(self) -> str:
        token = self.media_path_token.strip("/")
        if self.legacy_root:
            return f"{self.base_url}/{token}"
        return f"{self.base_url}/{token}/{self.slug}"

    def public_media_relative_path(self, processed_name: str) -> str:
        token = self.media_path_token.strip("/")
        if self.legacy_root:
            return f"{token}/episodes/{processed_name}"
        return f"{token}/{self.slug}/episodes/{processed_name}"

    @property
    def feed_url(self) -> str:
        return f"{self.public_base_url}/feed.xml"

    @property
    def index_url(self) -> str:
        return f"{self.public_base_url}/"

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.state_file.parent,
            self.downloads_dir,
            self.cache_dir,
            self.public_root_dir,
            self.public_dir,
            self.public_media_root_dir,
            self.public_episodes_dir,
            self.public_images_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class AppConfig:
    base_url: str
    output_dir: Path
    http: HTTPConfig
    podcasts: list[PodcastConfig]

    @property
    def public_dir(self) -> Path:
        return self.output_dir / "data" / "public"

    @property
    def public_index(self) -> Path:
        return self.public_dir / "index.html"

    def ensure_directories(self) -> None:
        self.public_dir.mkdir(parents=True, exist_ok=True)
        for podcast in self.podcasts:
            podcast.ensure_directories()


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    raw = _load_raw_config(config_path.resolve(), seen=set())
    base_url = str(raw["base_url"]).rstrip("/")
    output_dir = Path(raw["output_dir"]).expanduser()
    media_path_token = _parse_media_path_token(
        raw.get("media_path_token", DEFAULT_MEDIA_PATH_TOKEN)
    )
    http = _parse_http(raw.get("http", {}))
    ffmpeg = _parse_ffmpeg(raw.get("ffmpeg", {}))

    default_cache_artwork = bool(raw.get("cache_artwork", False))
    default_badge_artwork = bool(raw.get("badge_artwork", False))
    default_keep_original_downloads = bool(raw.get("keep_original_downloads", False))
    default_max_episodes = _parse_max_episodes(raw.get("max_episodes"))
    default_podcast_mode = _parse_podcast_mode(raw.get("podcast_mode", "auto"))

    podcasts_raw = raw.get("podcasts")
    podcasts: list[PodcastConfig]
    if podcasts_raw:
        podcasts = [
            _parse_podcast(
                item,
                base_url=base_url,
                output_dir=output_dir,
                cache_artwork=default_cache_artwork,
                badge_artwork=default_badge_artwork,
                keep_original_downloads=default_keep_original_downloads,
                max_episodes=default_max_episodes,
                podcast_mode=default_podcast_mode,
                media_path_token=media_path_token,
                http=http,
                ffmpeg=ffmpeg,
                legacy_root=False,
            )
            for item in podcasts_raw
        ]
    else:
        podcasts = [
            PodcastConfig(
                slug=_parse_slug(raw.get("slug") or "podcast"),
                upstream_feed_url=raw["upstream_feed_url"],
                base_url=base_url,
                output_dir=output_dir,
                keep_original_downloads=default_keep_original_downloads,
                cache_artwork=default_cache_artwork,
                badge_artwork=default_badge_artwork,
                max_episodes=default_max_episodes,
                podcast_mode=default_podcast_mode,
                media_path_token=media_path_token,
                http=http,
                ffmpeg=ffmpeg,
                legacy_root=True,
            )
        ]

    app_config = AppConfig(
        base_url=base_url,
        output_dir=output_dir,
        http=http,
        podcasts=podcasts,
    )
    app_config.ensure_directories()
    return app_config


def _load_raw_config(path: Path, *, seen: set[Path]) -> dict[str, Any]:
    resolved = path.resolve()
    if resolved in seen:
        raise ValueError(f"config include cycle detected at {resolved}")
    seen.add(resolved)
    try:
        raw = tomllib.loads(resolved.read_text(encoding="utf-8"))
        merged: dict[str, Any] = {}
        includes = raw.pop("include", [])
        include_paths = _normalize_includes(includes)
        for include_name in include_paths:
            include_path = (resolved.parent / include_name).resolve()
            included = _load_raw_config(include_path, seen=seen)
            merged = _merge_config_dicts(merged, included)
        return _merge_config_dicts(merged, raw)
    finally:
        seen.remove(resolved)


def _normalize_includes(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        includes: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("config include entries must be non-empty strings")
            includes.append(item)
        return includes
    raise ValueError("config include must be a string or list of strings")


def _merge_config_dicts(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if key not in merged:
            merged[key] = value
            continue
        current = merged[key]
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _merge_config_dicts(current, value)
        elif key == "podcasts" and isinstance(current, list) and isinstance(value, list):
            merged[key] = [*current, *value]
        else:
            merged[key] = value
    return merged


def _parse_http(raw: dict[str, object]) -> HTTPConfig:
    defaults = HTTPConfig()
    return HTTPConfig(
        user_agent=str(raw.get("user_agent", defaults.user_agent)),
        timeout_seconds=float(raw.get("timeout_seconds", defaults.timeout_seconds)),
        retries=int(raw.get("retries", defaults.retries)),
        basic_auth_username=str(
            raw.get("basic_auth_username", defaults.basic_auth_username)
        ),
        basic_auth_password=str(
            raw.get("basic_auth_password", defaults.basic_auth_password)
        ),
    )


def _parse_ffmpeg(raw: dict[str, object]) -> FFMpegConfig:
    defaults = FFMpegConfig()
    return FFMpegConfig(
        binary=str(raw.get("binary", defaults.binary)),
        highpass_hz=int(raw.get("highpass_hz", defaults.highpass_hz)),
        lowpass_hz=int(raw.get("lowpass_hz", defaults.lowpass_hz)),
        compressor_threshold_db=int(
            raw.get(
                "compressor_threshold_db",
                defaults.compressor_threshold_db,
            )
        ),
        compressor_ratio=str(raw.get("compressor_ratio", defaults.compressor_ratio)),
        attack_ms=int(raw.get("attack_ms", defaults.attack_ms)),
        release_ms=int(raw.get("release_ms", defaults.release_ms)),
        sample_rate_hz=int(raw.get("sample_rate_hz", defaults.sample_rate_hz)),
        bitrate_kbps=int(raw.get("bitrate_kbps", defaults.bitrate_kbps)),
        channels=int(raw.get("channels", defaults.channels)),
        normalize=bool(raw.get("normalize", defaults.normalize)),
        loudness_target_lufs=float(
            raw.get(
                "loudness_target_lufs",
                defaults.loudness_target_lufs,
            )
        ),
        true_peak_db=float(raw.get("true_peak_db", defaults.true_peak_db)),
        loudness_range_target=float(
            raw.get(
                "loudness_range_target",
                defaults.loudness_range_target,
            )
        ),
    )


def _ffmpeg_overrides(base: FFMpegConfig, raw: object) -> FFMpegConfig:
    if raw in (None, {}):
        return base
    if not isinstance(raw, dict):
        raise ValueError("podcast ffmpeg override must be an inline table/object")
    merged: dict[str, object] = {
        "binary": base.binary,
        "highpass_hz": base.highpass_hz,
        "lowpass_hz": base.lowpass_hz,
        "compressor_threshold_db": base.compressor_threshold_db,
        "compressor_ratio": base.compressor_ratio,
        "attack_ms": base.attack_ms,
        "release_ms": base.release_ms,
        "sample_rate_hz": base.sample_rate_hz,
        "bitrate_kbps": base.bitrate_kbps,
        "channels": base.channels,
        "normalize": base.normalize,
        "loudness_target_lufs": base.loudness_target_lufs,
        "true_peak_db": base.true_peak_db,
        "loudness_range_target": base.loudness_range_target,
    }
    merged.update(raw)
    return _parse_ffmpeg(merged)


def _parse_podcast(
    raw: dict[str, object],
    *,
    base_url: str,
    output_dir: Path,
    keep_original_downloads: bool,
    cache_artwork: bool,
    badge_artwork: bool,
    max_episodes: int | None,
    podcast_mode: FeedMode,
    media_path_token: str,
    http: HTTPConfig,
    ffmpeg: FFMpegConfig,
    legacy_root: bool,
) -> PodcastConfig:
    upstream_feed_url = str(raw["upstream_feed_url"])
    slug_value = raw.get("slug") or upstream_feed_url.rsplit("/", 2)[-2]
    return PodcastConfig(
        slug=_parse_slug(slug_value),
        upstream_feed_url=upstream_feed_url,
        episode_title_include=_parse_optional_pattern(raw.get("episode_title_include")),
        base_url=base_url,
        output_dir=output_dir,
        keep_original_downloads=bool(
            raw.get("keep_original_downloads", keep_original_downloads)
        ),
        cache_artwork=bool(raw.get("cache_artwork", cache_artwork)),
        badge_artwork=bool(raw.get("badge_artwork", badge_artwork)),
        max_episodes=_parse_max_episodes(raw.get("max_episodes", max_episodes)),
        podcast_mode=_parse_podcast_mode(raw.get("podcast_mode", podcast_mode)),
        media_path_token=media_path_token,
        http=http,
        ffmpeg=_ffmpeg_overrides(ffmpeg, raw.get("ffmpeg")),
        legacy_root=legacy_root,
    )


def _parse_podcast_mode(value: object) -> FeedMode:
    mode = str(value).strip().lower()
    if mode not in {"auto", "news", "story"}:
        raise ValueError("podcast_mode must be one of: auto, news, story")
    return mode


def _parse_max_episodes(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "unlimited", "all"}:
            return None
        return int(normalized)
    return int(value)


def _parse_slug(value: object) -> str:
    slug = sanitize_filename(str(value).strip().lower(), fallback="podcast")
    return slug.replace(".", "-")


def _parse_optional_pattern(value: object) -> str | None:
    if value is None:
        return None
    pattern = str(value).strip()
    if not pattern:
        return None
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"invalid regular expression {pattern!r}: {exc}") from exc
    return pattern


def _parse_media_path_token(value: object) -> str:
    token = sanitize_filename(str(value).strip(), fallback=DEFAULT_MEDIA_PATH_TOKEN)
    return token.strip("/")
