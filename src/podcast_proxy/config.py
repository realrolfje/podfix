from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

FeedMode = str


@dataclass(slots=True)
class HTTPConfig:
    user_agent: str = "podcast-proxy/0.1"
    timeout_seconds: float = 30.0
    retries: int = 2


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
class Config:
    upstream_feed_url: str
    base_url: str
    output_dir: Path
    cache_artwork: bool
    badge_artwork: bool
    max_episodes: int | None
    podcast_mode: FeedMode
    http: HTTPConfig
    ffmpeg: FFMpegConfig

    @property
    def data_dir(self) -> Path:
        return self.output_dir / "data"

    @property
    def state_file(self) -> Path:
        return self.data_dir / "state.json"

    @property
    def downloads_dir(self) -> Path:
        return self.data_dir / "downloads"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def public_dir(self) -> Path:
        return self.data_dir / "public"

    @property
    def public_feed(self) -> Path:
        return self.public_dir / "feed.xml"

    @property
    def public_episodes_dir(self) -> Path:
        return self.public_dir / "episodes"

    @property
    def public_images_dir(self) -> Path:
        return self.public_dir / "images"

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.downloads_dir,
            self.processed_dir,
            self.cache_dir,
            self.public_dir,
            self.public_episodes_dir,
            self.public_images_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


def load_config(path: str | Path) -> Config:
    config_path = Path(path)
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))

    http_raw = raw.get("http", {})
    ffmpeg_raw = raw.get("ffmpeg", {})

    config = Config(
        upstream_feed_url=raw["upstream_feed_url"],
        base_url=str(raw["base_url"]).rstrip("/"),
        output_dir=Path(raw["output_dir"]).expanduser(),
        cache_artwork=bool(raw.get("cache_artwork", False)),
        badge_artwork=bool(raw.get("badge_artwork", False)),
        max_episodes=raw.get("max_episodes"),
        podcast_mode=_parse_podcast_mode(raw.get("podcast_mode", "auto")),
        http=HTTPConfig(
            user_agent=http_raw.get("user_agent", HTTPConfig.user_agent),
            timeout_seconds=float(
                http_raw.get("timeout_seconds", HTTPConfig.timeout_seconds)
            ),
            retries=int(http_raw.get("retries", HTTPConfig.retries)),
        ),
        ffmpeg=FFMpegConfig(
            binary=ffmpeg_raw.get("binary", FFMpegConfig.binary),
            highpass_hz=int(ffmpeg_raw.get("highpass_hz", FFMpegConfig.highpass_hz)),
            lowpass_hz=int(ffmpeg_raw.get("lowpass_hz", FFMpegConfig.lowpass_hz)),
            compressor_threshold_db=int(
                ffmpeg_raw.get(
                    "compressor_threshold_db",
                    FFMpegConfig.compressor_threshold_db,
                )
            ),
            compressor_ratio=str(
                ffmpeg_raw.get("compressor_ratio", FFMpegConfig.compressor_ratio)
            ),
            attack_ms=int(ffmpeg_raw.get("attack_ms", FFMpegConfig.attack_ms)),
            release_ms=int(ffmpeg_raw.get("release_ms", FFMpegConfig.release_ms)),
            sample_rate_hz=int(
                ffmpeg_raw.get("sample_rate_hz", FFMpegConfig.sample_rate_hz)
            ),
            bitrate_kbps=int(ffmpeg_raw.get("bitrate_kbps", FFMpegConfig.bitrate_kbps)),
            channels=int(ffmpeg_raw.get("channels", FFMpegConfig.channels)),
            normalize=bool(ffmpeg_raw.get("normalize", FFMpegConfig.normalize)),
            loudness_target_lufs=float(
                ffmpeg_raw.get(
                    "loudness_target_lufs",
                    FFMpegConfig.loudness_target_lufs,
                )
            ),
            true_peak_db=float(
                ffmpeg_raw.get("true_peak_db", FFMpegConfig.true_peak_db)
            ),
            loudness_range_target=float(
                ffmpeg_raw.get(
                    "loudness_range_target",
                    FFMpegConfig.loudness_range_target,
                )
            ),
        ),
    )
    config.ensure_directories()
    return config


def _parse_podcast_mode(value: object) -> FeedMode:
    mode = str(value).strip().lower()
    if mode not in {"auto", "news", "story"}:
        raise ValueError("podcast_mode must be one of: auto, news, story")
    return mode
