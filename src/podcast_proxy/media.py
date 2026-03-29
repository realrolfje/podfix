from __future__ import annotations

from pathlib import Path
import subprocess

import requests

from .config import Config
from .feed import Episode


def download_media(
    session: requests.Session,
    config: Config,
    episode: Episode,
) -> Path:
    suffix = Path(episode.enclosure_url).suffix or ".bin"
    destination = config.downloads_dir / f"{episode.slug}{suffix}"
    if destination.exists():
        return destination

    with session.get(
        episode.enclosure_url,
        timeout=config.http.timeout_seconds,
        stream=True,
    ) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if chunk:
                    handle.write(chunk)
    return destination


def transcode_media(config: Config, source_path: Path, episode: Episode) -> Path:
    return transcode_media_with_options(
        config,
        source_path,
        episode,
        force=False,
    )


def transcode_media_with_options(
    config: Config,
    source_path: Path,
    episode: Episode,
    force: bool,
) -> Path:
    public_path = config.public_episodes_dir / f"{episode.slug}.mp3"
    if public_path.exists() and not force:
        _cleanup_source(source_path)
        return public_path
    if public_path.exists() and force:
        public_path.unlink()

    command = build_ffmpeg_command(config, source_path, public_path, episode.source_kind)
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffmpeg failed")

    _cleanup_source(source_path)
    return public_path


def build_ffmpeg_command(
    config: Config,
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


def _cleanup_source(source_path: Path) -> None:
    if source_path.exists():
        source_path.unlink()
