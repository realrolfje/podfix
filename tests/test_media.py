from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from podcast_proxy.config import FFMpegConfig, HTTPConfig, PodcastConfig
from podcast_proxy.feed import Episode
from podcast_proxy.media import download_media, transcode_media_with_options


class _ChunkedResponse:
    def __init__(self, chunks: list[bytes], error_at: int | None = None) -> None:
        self._chunks = chunks
        self._error_at = error_at

    def __enter__(self) -> _ChunkedResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def raise_for_status(self) -> None:
        return

    def iter_content(self, chunk_size: int) -> list[bytes]:
        del chunk_size
        for index, chunk in enumerate(self._chunks):
            if self._error_at == index:
                raise KeyboardInterrupt()
            yield chunk


class _Session:
    def __init__(self, response: _ChunkedResponse) -> None:
        self._response = response

    def get(self, url: str, *, timeout: float, stream: bool) -> _ChunkedResponse:
        del url, timeout, stream
        return self._response


class MediaSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.config = PodcastConfig(
            slug="test-show",
            upstream_feed_url="https://example.com/feed.xml",
            episode_title_include=None,
            base_url="http://localhost:8080",
            output_dir=root,
            keep_original_downloads=False,
            cache_artwork=False,
            badge_artwork=False,
            max_episodes=5,
            podcast_mode="news",
            media_path_token="media-change-me",
            http=HTTPConfig(),
            ffmpeg=FFMpegConfig(binary="ffmpeg"),
        )
        self.config.ensure_directories()
        self.episode = Episode(
            guid="ep-1",
            title="Episode 1",
            description="",
            published="Wed, 01 Apr 2026 06:00:00 +0200",
            enclosure_url="https://example.com/audio.mp3",
            enclosure_type="audio/mpeg",
            source_kind="audio",
            slug="episode-1",
            author=None,
            original_link=None,
            image_url=None,
            explicit="false",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_download_cleans_up_partial_file_on_interrupt(self) -> None:
        destination = self.config.downloads_dir / "episode-1.mp3"
        temp_path = destination.with_name("episode-1.part.mp3")
        session = _Session(_ChunkedResponse([b"abc", b"def"], error_at=1))

        with self.assertRaises(KeyboardInterrupt):
            download_media(session, self.config, self.episode)

        self.assertFalse(destination.exists())
        self.assertFalse(temp_path.exists())

    def test_rebuild_failure_keeps_existing_public_mp3(self) -> None:
        source_path = self.config.downloads_dir / "episode-1.mp3"
        source_path.write_bytes(b"source")
        public_path = self.config.public_episodes_dir / "episode-1.mp3"
        public_path.write_bytes(b"existing-public")
        temp_path = public_path.with_name("episode-1.part.mp3")

        with patch("podcast_proxy.media.subprocess.run") as mocked_run:
            mocked_run.return_value.returncode = 1
            mocked_run.return_value.stderr = "ffmpeg failed"
            with self.assertRaisesRegex(RuntimeError, "ffmpeg failed"):
                transcode_media_with_options(
                    self.config,
                    source_path,
                    self.episode,
                    force=True,
                )

        self.assertEqual(public_path.read_bytes(), b"existing-public")
        self.assertTrue(source_path.exists())
        self.assertFalse(temp_path.exists())

    def test_rebuild_success_replaces_public_mp3_atomically(self) -> None:
        source_path = self.config.downloads_dir / "episode-1.mp3"
        source_path.write_bytes(b"source")
        public_path = self.config.public_episodes_dir / "episode-1.mp3"
        public_path.write_bytes(b"old-public")

        def fake_run(command: list[str], capture_output: bool, text: bool, check: bool):
            del capture_output, text, check
            output_path = Path(command[-1])
            output_path.write_bytes(b"new-public")

            class Result:
                returncode = 0
                stderr = ""

            return Result()

        with patch("podcast_proxy.media.subprocess.run", side_effect=fake_run):
            result = transcode_media_with_options(
                self.config,
                source_path,
                self.episode,
                force=True,
            )

        self.assertEqual(result, public_path)
        self.assertEqual(public_path.read_bytes(), b"new-public")
        self.assertFalse(source_path.exists())
        self.assertFalse(public_path.with_name("episode-1.part.mp3").exists())


if __name__ == "__main__":
    unittest.main()
