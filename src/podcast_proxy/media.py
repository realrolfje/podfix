from __future__ import annotations

from pathlib import Path
import subprocess

import requests

from .config import PodcastConfig
from .feed import Episode


def download_media(
    session: requests.Session,
    config: PodcastConfig,
    episode: Episode,
) -> Path:
    suffix = Path(episode.enclosure_url).suffix or ".bin"
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
    public_path = config.public_episodes_dir / f"{episode.slug}.mp3"
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


def ensure_public_episode_path(
    config: PodcastConfig,
    processed_name: str,
) -> Path | None:
    public_path = config.public_episodes_dir / processed_name
    if public_path.exists():
        return public_path
    legacy_path = config.legacy_public_episodes_dir / processed_name
    if not legacy_path.exists():
        return None
    public_path.parent.mkdir(parents=True, exist_ok=True)
    legacy_path.replace(public_path)
    return public_path
