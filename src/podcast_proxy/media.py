from __future__ import annotations

from pathlib import Path
import subprocess
from urllib.parse import urlsplit

import requests

from .config import PodcastConfig
from .feed import Episode


def download_media(
    session: requests.Session,
    config: PodcastConfig,
    episode: Episode,
) -> Path:
    suffix = _download_suffix(episode.enclosure_url)
    destination = config.downloads_dir / f"{episode.slug}{suffix}"
    if destination.exists():
        return destination
    temp_path = _temporary_path(destination)
    if temp_path.exists():
        temp_path.unlink()

    try:
        with session.get(
            episode.enclosure_url,
            timeout=config.http.timeout_seconds,
            stream=True,
        ) as response:
            response.raise_for_status()
            with temp_path.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if chunk:
                        handle.write(chunk)
        temp_path.replace(destination)
    except BaseException:
        if temp_path.exists():
            temp_path.unlink()
        raise
    return destination


def transcode_media(config: PodcastConfig, source_path: Path, episode: Episode) -> Path:
    return transcode_media_with_options(
        config,
        source_path,
        episode,
        force=False,
    )


def transcode_media_with_options(
    config: PodcastConfig,
    source_path: Path,
    episode: Episode,
    force: bool,
) -> Path:
    public_path = config.public_episodes_dir / config.published_episode_filename(episode.guid)
    migrated_path = ensure_public_episode_path(config, public_path.name)
    if migrated_path is not None:
        public_path = migrated_path
    if public_path.exists() and not force:
        _cleanup_source(config, source_path)
        return public_path
    temp_path = _temporary_path(public_path)
    if temp_path.exists():
        temp_path.unlink()

    command = build_ffmpeg_command(config, source_path, temp_path, episode.source_kind)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "ffmpeg failed")
        temp_path.replace(public_path)
    except BaseException:
        if temp_path.exists():
            temp_path.unlink()
        raise

    _cleanup_source(config, source_path)
    return public_path


def build_ffmpeg_command(
    config: PodcastConfig,
    source_path: Path,
    output_path: Path,
    source_kind: str,
) -> list[str]:
    ffmpeg = config.ffmpeg
    filters = [
        f"highpass=f={ffmpeg.highpass_hz},"
        f"lowpass=f={ffmpeg.lowpass_hz},"
        f"acompressor=threshold={ffmpeg.compressor_threshold_db}dB:"
        f"ratio={ffmpeg.compressor_ratio}:attack={ffmpeg.attack_ms}:"
        f"release={ffmpeg.release_ms}",
    ]
    if ffmpeg.normalize:
        filters.append(
            f"loudnorm=I={ffmpeg.loudness_target_lufs}:"
            f"TP={ffmpeg.true_peak_db}:"
            f"LRA={ffmpeg.loudness_range_target}"
        )
    audio_filter = ",".join(filters)
    command = [
        ffmpeg.binary,
        "-y",
        "-i",
        str(source_path),
    ]
    if source_kind == "video":
        command.extend(["-vn"])
    command.extend(
        [
            "-af",
            audio_filter,
            "-ar",
            str(ffmpeg.sample_rate_hz),
            "-ac",
            str(ffmpeg.channels),
            "-b:a",
            f"{ffmpeg.bitrate_kbps}k",
            "-codec:a",
            "libmp3lame",
            str(output_path),
        ]
    )
    return command


def _cleanup_source(config: PodcastConfig, source_path: Path) -> None:
    if config.keep_original_downloads:
        return
    if source_path.exists():
        source_path.unlink()


def _temporary_path(path: Path) -> Path:
    if path.suffix:
        return path.with_name(f"{path.stem}.part{path.suffix}")
    return path.with_name(f"{path.name}.part")


def _download_suffix(enclosure_url: str) -> str:
    path = urlsplit(enclosure_url).path
    return Path(path).suffix or ".bin"


def ensure_public_episode_path(
    config: PodcastConfig,
    processed_name: str,
    published_relative_path: str | None = None,
    target_processed_name: str | None = None,
    target_relative_path: str | None = None,
) -> Path | None:
    resolved_processed_name = target_processed_name or processed_name
    resolved_relative_path = target_relative_path or published_relative_path
    if resolved_relative_path:
        public_path = config.public_root_dir / resolved_relative_path
    else:
        public_path = config.public_episodes_dir / resolved_processed_name
    if public_path.exists():
        return public_path
    current_paths: list[Path] = []
    if published_relative_path:
        current_paths.append(config.public_root_dir / published_relative_path)
    current_paths.append(config.public_episodes_dir / processed_name)
    current_paths.append(config.legacy_public_episodes_dir / processed_name)
    seen: set[Path] = set()
    for current_path in current_paths:
        if current_path in seen:
            continue
        seen.add(current_path)
        if not current_path.exists():
            continue
        public_path.parent.mkdir(parents=True, exist_ok=True)
        if current_path != public_path:
            current_path.replace(public_path)
        return public_path
    return None
