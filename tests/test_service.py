from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from podcast_proxy.config import FFMpegConfig, HTTPConfig, PodcastConfig
from podcast_proxy.feed import Episode
from podcast_proxy.service import (
    _ensure_public_files_for_records,
    _next_enclosure_url_version,
    _normalize_record_urls,
    _prepare_episode_state_for_render,
    _rebuild_episode_artwork,
)


class RebuildImagesTests(unittest.TestCase):
    def test_rebuild_images_refreshes_enclosure_url_from_public_media_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="losse-eindjes",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=False,
                badge_artwork=False,
                max_episodes=5,
                podcast_mode="news",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )
            episode = Episode(
                guid="WO_KN_20309964",
                title="Nieuwe Podcast: Losse Eindjes",
                description="",
                published="Thu, 11 Dec 2025 15:47:00 +0100",
                enclosure_url="https://upstream.example.com/audio.mp3",
                enclosure_type="audio/mpeg",
                source_kind="audio",
                slug="episode",
                author=None,
                original_link=None,
                image_url=None,
                explicit="false",
            )
            episode_state = {
                episode.guid: {
                    "guid": episode.guid,
                    "processed_file": "Thu-11-Dec-2025-15-47-00-0100-Nieuwe-Podcast-Losse-Eindjes-WO_KN_20309964.mp3",
                    "public_media_file": "media-change-me/losse-eindjes/episodes/Thu-11-Dec-2025-15-47-00-0100-Nieuwe-Podcast-Losse-Eindjes-WO_KN_20309964.mp3",
                    "enclosure_url": "http://static.example.com/private/podfix/data/published/losse-eindjes/episodes/Thu-11-Dec-2025-15-47-00-0100-Nieuwe-Podcast-Losse-Eindjes-WO_KN_20309964.mp3",
                    "image_url": None,
                }
            }

            rebuilt = _rebuild_episode_artwork(
                session=None,
                config=config,
                episodes=[episode],
                episode_state=episode_state,
                resolved_mode="news",
                enclosure_url_version=0,
            )

        self.assertEqual(
            rebuilt[episode.guid]["enclosure_url"],
            "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/Thu-11-Dec-2025-15-47-00-0100-Nieuwe-Podcast-Losse-Eindjes-WO_KN_20309964.mp3",
        )

    def test_rebuild_images_uses_versioned_enclosure_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="losse-eindjes",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=False,
                badge_artwork=False,
                max_episodes=5,
                podcast_mode="news",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )
            episode = Episode(
                guid="WO_KN_20309964",
                title="Nieuwe Podcast: Losse Eindjes",
                description="",
                published="Thu, 11 Dec 2025 15:47:00 +0100",
                enclosure_url="https://upstream.example.com/audio.mp3",
                enclosure_type="audio/mpeg",
                source_kind="audio",
                slug="episode",
                author=None,
                original_link=None,
                image_url=None,
                explicit="false",
            )
            episode_state = {
                episode.guid: {
                    "guid": episode.guid,
                    "processed_file": "Thu-11-Dec-2025-15-47-00-0100-Nieuwe-Podcast-Losse-Eindjes-WO_KN_20309964.mp3",
                    "public_media_file": "media-change-me/losse-eindjes/episodes/Thu-11-Dec-2025-15-47-00-0100-Nieuwe-Podcast-Losse-Eindjes-WO_KN_20309964.mp3",
                    "enclosure_url": "https://static.example.com/private/podfix/data/published/losse-eindjes/episodes/Thu-11-Dec-2025-15-47-00-0100-Nieuwe-Podcast-Losse-Eindjes-WO_KN_20309964.mp3",
                    "image_url": None,
                }
            }

            rebuilt = _rebuild_episode_artwork(
                session=None,
                config=config,
                episodes=[episode],
                episode_state=episode_state,
                resolved_mode="news",
                enclosure_url_version=2,
            )

        self.assertEqual(
            rebuilt[episode.guid]["enclosure_url"],
            "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/Thu-11-Dec-2025-15-47-00-0100-Nieuwe-Podcast-Losse-Eindjes-WO_KN_20309964.mp3?v=2",
        )

    def test_normalize_record_urls_prefers_public_media_file_and_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="losse-eindjes",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=False,
                badge_artwork=False,
                max_episodes=5,
                podcast_mode="news",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )

            normalized = _normalize_record_urls(
                config,
                {
                    "public_media_file": "media-change-me/losse-eindjes/episodes/episode.mp3",
                    "processed_file": "episode.mp3",
                    "enclosure_url": "https://old.example.com/stale.mp3",
                },
                3,
            )

        self.assertEqual(
            normalized["enclosure_url"],
            "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/episode.mp3?v=3",
        )

    def test_rebuild_bumps_enclosure_url_version(self) -> None:
        self.assertEqual(_next_enclosure_url_version({}, rebuild=False), 0)
        self.assertEqual(_next_enclosure_url_version({}, rebuild=True), 1)
        self.assertEqual(
            _next_enclosure_url_version({"enclosure_url_version": 4}, rebuild=False),
            4,
        )
        self.assertEqual(
            _next_enclosure_url_version({"enclosure_url_version": 4}, rebuild=True),
            5,
        )

    def test_ensure_public_files_for_records_moves_legacy_episode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="losse-eindjes",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=False,
                badge_artwork=False,
                max_episodes=5,
                podcast_mode="news",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )
            config.ensure_directories()
            legacy_path = config.legacy_public_episodes_dir / "episode.mp3"
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_path.write_bytes(b"legacy-public")

            _ensure_public_files_for_records(
                config,
                [{"processed_file": "episode.mp3"}],
            )

            self.assertEqual(
                (config.public_episodes_dir / "episode.mp3").read_bytes(),
                b"legacy-public",
            )
            self.assertFalse(legacy_path.exists())

    def test_ensure_public_files_for_records_preserves_state_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="losse-eindjes",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=False,
                badge_artwork=False,
                max_episodes=5,
                podcast_mode="news",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )
            config.ensure_directories()
            legacy_path = config.legacy_public_episodes_dir / "episode.mp3"
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            legacy_path.write_bytes(b"legacy-public")
            record = {
                "processed_file": "episode.mp3",
                "public_media_file": "media-change-me/losse-eindjes/episodes/episode.mp3",
            }

            _ensure_public_files_for_records(config, [record])

            self.assertEqual(
                record["public_media_file"],
                "media-change-me/losse-eindjes/episodes/episode.mp3",
            )

    def test_prepare_episode_state_for_render_backfills_public_media_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="losse-eindjes",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=False,
                badge_artwork=False,
                max_episodes=5,
                podcast_mode="news",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )
            episode_state = {
                "guid-1": {
                    "guid": "guid-1",
                    "processed_file": "episode.mp3",
                    "enclosure_url": "http://static.example.com/private/podfix/data/published/losse-eindjes/episodes/episode.mp3",
                }
            }

            changed = _prepare_episode_state_for_render(config, episode_state, 2)

            self.assertTrue(changed)
            self.assertEqual(
                episode_state["guid-1"]["public_media_file"],
                "media-change-me/losse-eindjes/episodes/episode.mp3",
            )
            self.assertEqual(
                episode_state["guid-1"]["enclosure_url"],
                "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/episode.mp3?v=2",
            )

    def test_normalize_record_urls_upgrades_legacy_local_episode_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="losse-eindjes",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=False,
                badge_artwork=False,
                max_episodes=5,
                podcast_mode="news",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )

            normalized = _normalize_record_urls(
                config,
                {
                    "enclosure_url": "https://static.example.com/private/podfix/data/published/episodes/episode.mp3",
                },
                1,
            )

        self.assertEqual(
            normalized["enclosure_url"],
            "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/episode.mp3?v=1",
        )


if __name__ == "__main__":
    unittest.main()
