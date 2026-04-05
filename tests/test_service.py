from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from podcast_proxy.config import FFMpegConfig, HTTPConfig, PodcastConfig
from podcast_proxy.feed import Episode
from podcast_proxy.rss import write_feed
from podcast_proxy.service import (
    _ensure_public_files_for_records,
    _next_enclosure_url_version,
    _normalize_record_urls,
    _prepare_episode_state_for_render,
    _report_stale_public_files,
    _rebuild_episode_artwork,
)
from podcast_proxy.state import StateStore


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
            "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/WO_KN_20309964.mp3",
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
            "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/WO_KN_20309964.mp3?v=2",
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
                [{"guid": "guid-1", "processed_file": "episode.mp3"}],
            )

            self.assertEqual(
                (config.public_episodes_dir / "guid-1.mp3").read_bytes(),
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

            self.assertEqual(record["processed_file"], "episode.mp3")
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
                episode_state["guid-1"]["processed_file"],
                "guid-1.mp3",
            )
            self.assertEqual(
                episode_state["guid-1"]["public_media_file"],
                "media-change-me/losse-eindjes/episodes/guid-1.mp3",
            )
            self.assertEqual(
                episode_state["guid-1"]["enclosure_url"],
                "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/guid-1.mp3?v=2",
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

    def test_prepare_episode_state_for_render_renames_existing_processed_file_to_guid(
        self,
    ) -> None:
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
            old_path = config.public_episodes_dir / "old-name.mp3"
            old_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.write_bytes(b"audio")
            episode_state = {
                "WO_KN_20309964": {
                    "guid": "WO_KN_20309964",
                    "processed_file": "old-name.mp3",
                    "public_media_file": "media-change-me/losse-eindjes/episodes/old-name.mp3",
                    "enclosure_url": "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/old-name.mp3",
                }
            }

            changed = _prepare_episode_state_for_render(config, episode_state, 0)

            self.assertTrue(changed)
            self.assertEqual(
                episode_state["WO_KN_20309964"]["processed_file"],
                "WO_KN_20309964.mp3",
            )
            self.assertEqual(
                episode_state["WO_KN_20309964"]["public_media_file"],
                "media-change-me/losse-eindjes/episodes/WO_KN_20309964.mp3",
            )
            self.assertEqual(
                (config.public_episodes_dir / "WO_KN_20309964.mp3").read_bytes(),
                b"audio",
            )
            self.assertFalse(old_path.exists())

    def test_report_stale_public_files_logs_orphaned_mp3(self) -> None:
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
            config.public_feed.write_text("feed", encoding="utf-8")
            config.public_index.write_text("index", encoding="utf-8")
            orphan_path = config.public_episodes_dir / "orphan.mp3"
            orphan_path.parent.mkdir(parents=True, exist_ok=True)
            orphan_path.write_bytes(b"orphan")

            with self.assertLogs("podcast_proxy.service", level="WARNING") as captured:
                _report_stale_public_files(config, {}, [])

        self.assertIn("stale published file for losse-eindjes", captured.output[0])
        self.assertIn("orphan.mp3", captured.output[0])

    def test_report_stale_public_files_deletes_orphaned_mp3_when_requested(self) -> None:
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
            config.public_feed.write_text("feed", encoding="utf-8")
            config.public_index.write_text("index", encoding="utf-8")
            orphan_path = config.public_episodes_dir / "orphan.mp3"
            orphan_path.parent.mkdir(parents=True, exist_ok=True)
            orphan_path.write_bytes(b"orphan")

            with self.assertLogs("podcast_proxy.service", level="WARNING") as captured:
                _report_stale_public_files(config, {}, [], delete_files=True)

        self.assertIn("deleted stale published file for losse-eindjes", captured.output[0])
        self.assertIn("orphan.mp3", captured.output[0])
        self.assertFalse(orphan_path.exists())

    def test_guid_filename_migration_persists_state_and_feed(self) -> None:
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
            old_path = config.public_episodes_dir / "old-name.mp3"
            old_path.parent.mkdir(parents=True, exist_ok=True)
            old_path.write_bytes(b"audio")
            state = {
                "feed": {
                    "metadata": {
                        "title": "Losse eindjes",
                        "description": "desc",
                        "resolved_mode": "news",
                    }
                },
                "episodes": {
                    "WO_KN_20309964": {
                        "guid": "WO_KN_20309964",
                        "title": "Episode",
                        "description": "desc",
                        "published": "Thu, 11 Dec 2025 15:47:00 +0100",
                        "processed_file": "old-name.mp3",
                        "public_media_file": "media-change-me/losse-eindjes/episodes/old-name.mp3",
                        "enclosure_url": "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/old-name.mp3",
                        "enclosure_length": 5,
                        "enclosure_type": "audio/mpeg",
                    }
                },
            }

            changed = _prepare_episode_state_for_render(config, state["episodes"], 0)
            self.assertTrue(changed)
            records = [
                _normalize_record_urls(config, record, 0)
                for record in state["episodes"].values()
            ]
            write_feed(config, state["feed"]["metadata"], records)
            StateStore(config.state_file).save(state)
            reloaded = StateStore(config.state_file).load()

            migrated = reloaded["episodes"]["WO_KN_20309964"]
            self.assertEqual(migrated["processed_file"], "WO_KN_20309964.mp3")
            self.assertEqual(
                migrated["public_media_file"],
                "media-change-me/losse-eindjes/episodes/WO_KN_20309964.mp3",
            )
            self.assertFalse(old_path.exists())
            self.assertTrue((config.public_episodes_dir / "WO_KN_20309964.mp3").exists())

            root = ET.fromstring(config.public_feed.read_text(encoding="utf-8"))
            enclosure = root.find("./channel/item/enclosure")
            self.assertIsNotNone(enclosure)
            self.assertEqual(
                enclosure.attrib["url"],
                "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/WO_KN_20309964.mp3",
            )


if __name__ == "__main__":
    unittest.main()
