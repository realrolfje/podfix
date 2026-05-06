from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from podcast_proxy.config import FFMpegConfig, HTTPConfig, PodcastConfig
from podcast_proxy.feed import Episode, FeedSnapshot
from podcast_proxy.rss import write_feed
from podcast_proxy.service import (
    _available_episode_records,
    _drop_unavailable_episode_state,
    _ensure_public_files_for_records,
    _next_enclosure_url_version,
    _normalize_metadata_urls,
    _normalize_record_urls,
    _episodes_to_process,
    _prepare_episode_state_for_render,
    _renderable_records,
    _report_stale_public_files,
    _rebuild_episode_artwork,
    _sort_episodes,
    _sync_podcast,
)
from podcast_proxy.state import StateStore


class RebuildImagesTests(unittest.TestCase):
    def test_story_renderable_records_group_by_season_before_publish_date(self) -> None:
        records = [
            {
                "guid": "s3e1",
                "title": "Season 3 Episode 1",
                "published": "Sat, 25 Jan 2025 05:00:00 +0000",
                "season_number": 3,
                "episode_number": 1,
            },
            {
                "guid": "s1e10",
                "title": "Season 1 Episode 10",
                "published": "Tue, 25 Mar 2025 21:04:20 +0000",
                "season_number": 1,
                "episode_number": 10,
            },
            {
                "guid": "s1e8",
                "title": "Season 1 Episode 8",
                "published": "Tue, 11 Feb 2025 05:00:00 +0000",
                "season_number": 1,
                "episode_number": 8,
            },
            {
                "guid": "s2e1",
                "title": "Season 2 Episode 1",
                "published": "Tue, 08 Oct 2024 04:00:00 +0000",
                "season_number": 2,
                "episode_number": 1,
            },
        ]

        ordered = _renderable_records(records, resolved_mode="story", max_episodes=None)

        self.assertEqual(
            [record["guid"] for record in ordered],
            ["s1e8", "s1e10", "s2e1", "s3e1"],
        )

    def test_story_sort_uses_episode_number_to_break_same_publish_date(self) -> None:
        episodes = [
            Episode(
                guid="s2e2",
                title="Season 2 Episode 2",
                description="",
                published="Tue, 08 Oct 2024 04:00:00 +0000",
                enclosure_url="https://upstream.example.com/2.mp3",
                enclosure_type="audio/mpeg",
                source_kind="audio",
                slug="s2e2",
                author=None,
                original_link=None,
                image_url=None,
                explicit="false",
                season_number=2,
                episode_number=2,
            ),
            Episode(
                guid="s2e1",
                title="Season 2 Episode 1",
                description="",
                published="Tue, 08 Oct 2024 04:00:00 +0000",
                enclosure_url="https://upstream.example.com/1.mp3",
                enclosure_type="audio/mpeg",
                source_kind="audio",
                slug="s2e1",
                author=None,
                original_link=None,
                image_url=None,
                explicit="false",
                season_number=2,
                episode_number=1,
            ),
        ]

        ordered = _sort_episodes(episodes, resolved_mode="story")

        self.assertEqual([episode.guid for episode in ordered], ["s2e1", "s2e2"])

    def test_sync_processes_one_missing_episode_by_default(self) -> None:
        episodes = [
            Episode(
                guid=f"guid-{index}",
                title=f"Episode {index}",
                description="",
                published=f"Thu, {index:02d} Dec 2025 15:47:00 +0100",
                enclosure_url=f"https://upstream.example.com/{index}.mp3",
                enclosure_type="audio/mpeg",
                source_kind="audio",
                slug=f"episode-{index}",
                author=None,
                original_link=None,
                image_url=None,
                explicit="false",
            )
            for index in range(3, 0, -1)
        ]

        to_process = _episodes_to_process(
            episodes,
            episode_state={},
            resolved_mode="news",
            previous_mode="news",
            max_episodes=5,
            rebuild=False,
            process_all_episodes=False,
        )

        self.assertEqual([episode.guid for episode in to_process], ["guid-3"])

    def test_sync_processes_all_missing_episodes_when_requested(self) -> None:
        episodes = [
            Episode(
                guid=f"guid-{index}",
                title=f"Episode {index}",
                description="",
                published=f"Thu, {index:02d} Dec 2025 15:47:00 +0100",
                enclosure_url=f"https://upstream.example.com/{index}.mp3",
                enclosure_type="audio/mpeg",
                source_kind="audio",
                slug=f"episode-{index}",
                author=None,
                original_link=None,
                image_url=None,
                explicit="false",
            )
            for index in range(5, 0, -1)
        ]
        episode_state = {
            "guid-5": {
                "guid": "guid-5",
                "signature": "guid-5|audio/mpeg|Thu, 05 Dec 2025 15:47:00 +0100|Episode 5",
            }
        }

        to_process = _episodes_to_process(
            episodes,
            episode_state=episode_state,
            resolved_mode="news",
            previous_mode="news",
            max_episodes=3,
            rebuild=False,
            process_all_episodes=True,
        )

        self.assertEqual([episode.guid for episode in to_process], ["guid-4", "guid-3"])

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

    def test_prepare_episode_state_for_render_clears_missing_local_artwork(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="losse-eindjes",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=True,
                badge_artwork=False,
                max_episodes=5,
                podcast_mode="news",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )
            config.ensure_directories()
            episode_state = {
                "guid-1": {
                    "guid": "guid-1",
                    "processed_file": "guid-1.mp3",
                    "public_media_file": "media-change-me/losse-eindjes/episodes/guid-1.mp3",
                    "enclosure_url": "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/guid-1.mp3",
                    "image_url": "https://static.example.com/private/podfix/data/published/losse-eindjes/images/missing.jpg",
                }
            }
            public_episode = config.public_episodes_dir / "guid-1.mp3"
            public_episode.parent.mkdir(parents=True, exist_ok=True)
            public_episode.write_bytes(b"audio")

            with self.assertLogs("podcast_proxy.service", level="WARNING") as captured:
                changed = _prepare_episode_state_for_render(config, episode_state, 0)

            self.assertTrue(changed)
            self.assertIsNone(episode_state["guid-1"]["image_url"])
            self.assertIn("clearing missing local artwork reference", captured.output[0])

    def test_normalize_metadata_urls_clears_missing_local_artwork(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="losse-eindjes",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=True,
                badge_artwork=False,
                max_episodes=5,
                podcast_mode="news",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )
            config.ensure_directories()

            with self.assertLogs("podcast_proxy.service", level="WARNING") as captured:
                normalized = _normalize_metadata_urls(
                    config,
                    {
                        "title": "Losse eindjes",
                        "image_url": "https://static.example.com/private/podfix/data/published/losse-eindjes/images/missing.jpg",
                    },
                )

            self.assertIsNone(normalized["image_url"])
            self.assertIn("clearing missing local artwork reference", captured.output[0])

    def test_sync_refreshes_missing_local_artwork_for_existing_episode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="losse-eindjes",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=True,
                badge_artwork=False,
                max_episodes=5,
                podcast_mode="news",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )
            config.ensure_directories()
            public_episode = config.public_episodes_dir / "guid-1.mp3"
            public_episode.parent.mkdir(parents=True, exist_ok=True)
            public_episode.write_bytes(b"audio")

            episode = Episode(
                guid="guid-1",
                title="Available episode",
                description="desc",
                published="Thu, 11 Dec 2025 15:47:00 +0100",
                enclosure_url="https://upstream.example.com/audio.mp3",
                enclosure_type="audio/mpeg",
                source_kind="audio",
                slug="episode",
                author=None,
                original_link=None,
                image_url="https://upstream.example.com/art.jpg",
                explicit="false",
            )
            state = {
                "feed": {
                    "metadata": {
                        "title": "Losse eindjes",
                        "description": "desc",
                        "resolved_mode": "news",
                    }
                },
                "episodes": {
                    "guid-1": {
                        "guid": "guid-1",
                        "title": "Available episode",
                        "description": "desc",
                        "published": "Thu, 11 Dec 2025 15:47:00 +0100",
                        "processed_file": "guid-1.mp3",
                        "public_media_file": "media-change-me/losse-eindjes/episodes/guid-1.mp3",
                        "enclosure_url": "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/guid-1.mp3",
                        "enclosure_length": 5,
                        "enclosure_type": "audio/mpeg",
                        "image_url": "https://static.example.com/private/podfix/data/published/losse-eindjes/images/missing.jpg",
                        "signature": "guid-1|audio/mpeg|Thu, 11 Dec 2025 15:47:00 +0100|Available episode",
                        "source_signature": "https://upstream.example.com/audio.mp3|audio/mpeg|Thu, 11 Dec 2025 15:47:00 +0100|Available episode",
                    }
                },
            }
            StateStore(config.state_file).save(state)
            refreshed_image_url = (
                "https://static.example.com/private/podfix/data/published/losse-eindjes/images/refreshed.jpg"
            )
            refreshed_image = config.public_images_dir / "refreshed.jpg"
            refreshed_image.parent.mkdir(parents=True, exist_ok=True)
            refreshed_image.write_bytes(b"art")

            with (
                patch("podcast_proxy.service.make_session", return_value=object()),
                patch(
                    "podcast_proxy.service.fetch_feed",
                    return_value=FeedSnapshot(
                        metadata={
                            "title": "Losse eindjes",
                            "description": "desc",
                            "resolved_mode": "news",
                        },
                        episodes=[episode],
                        etag="etag-1",
                        last_modified="last-modified-1",
                        resolved_mode="news",
                    ),
                ),
                patch(
                    "podcast_proxy.service._process_episode_artwork",
                    return_value=refreshed_image_url,
                ) as process_episode_artwork,
                patch("podcast_proxy.service.write_feed"),
                patch("podcast_proxy.service.write_podcast_index"),
                patch("podcast_proxy.service.write_library_index"),
            ):
                summary = _sync_podcast(
                    config,
                    rebuild=False,
                    rebuild_images=False,
                    clean_stale=False,
                    process_all_episodes=False,
                )

            saved_state = StateStore(config.state_file).load()
            self.assertEqual(summary["episode_count"], 1)
            self.assertEqual(
                saved_state["episodes"]["guid-1"]["image_url"],
                refreshed_image_url,
            )
            process_episode_artwork.assert_called_once_with(
                unittest.mock.ANY,
                config,
                "https://upstream.example.com/art.jpg",
            )

    def test_sync_backfills_episode_metadata_for_existing_episode_without_reprocessing(self) -> None:
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
            public_episode = config.public_episodes_dir / "guid-1.mp3"
            public_episode.parent.mkdir(parents=True, exist_ok=True)
            public_episode.write_bytes(b"audio")

            episode = Episode(
                guid="guid-1",
                title="Available episode",
                description="desc",
                published="Thu, 11 Dec 2025 15:47:00 +0100",
                enclosure_url="https://upstream.example.com/audio.mp3",
                enclosure_type="audio/mpeg",
                source_kind="audio",
                slug="episode",
                author=None,
                original_link=None,
                image_url=None,
                explicit="false",
                episode_number=7,
                season_number=2,
                episode_type="full",
                duration_seconds=3723,
            )
            state = {
                "feed": {
                    "metadata": {
                        "title": "Losse eindjes",
                        "description": "desc",
                        "resolved_mode": "news",
                    }
                },
                "episodes": {
                    "guid-1": {
                        "guid": "guid-1",
                        "title": "Available episode",
                        "description": "desc",
                        "published": "Thu, 11 Dec 2025 15:47:00 +0100",
                        "processed_file": "guid-1.mp3",
                        "public_media_file": "media-change-me/losse-eindjes/episodes/guid-1.mp3",
                        "enclosure_url": "https://static.example.com/private/podfix/data/published/media-change-me/losse-eindjes/episodes/guid-1.mp3",
                        "enclosure_length": 5,
                        "enclosure_type": "audio/mpeg",
                        "signature": "guid-1|audio/mpeg|Thu, 11 Dec 2025 15:47:00 +0100|Available episode",
                        "source_signature": "https://upstream.example.com/audio.mp3|audio/mpeg|Thu, 11 Dec 2025 15:47:00 +0100|Available episode",
                    }
                },
            }
            StateStore(config.state_file).save(state)

            with (
                patch("podcast_proxy.service.make_session", return_value=object()),
                patch(
                    "podcast_proxy.service.fetch_feed",
                    return_value=FeedSnapshot(
                        metadata={
                            "title": "Losse eindjes",
                            "description": "desc",
                            "resolved_mode": "news",
                        },
                        episodes=[episode],
                        etag="etag-1",
                        last_modified="last-modified-1",
                        resolved_mode="news",
                    ),
                ),
                patch("podcast_proxy.service.download_media") as download_media,
                patch("podcast_proxy.service.transcode_media_with_options") as transcode,
                patch("podcast_proxy.service.write_feed"),
                patch("podcast_proxy.service.write_podcast_index"),
                patch("podcast_proxy.service.write_library_index"),
            ):
                summary = _sync_podcast(
                    config,
                    rebuild=False,
                    rebuild_images=False,
                    clean_stale=False,
                    process_all_episodes=False,
                )

            saved_state = StateStore(config.state_file).load()
            self.assertEqual(summary["episode_count"], 1)
            self.assertEqual(saved_state["episodes"]["guid-1"]["episode_number"], 7)
            self.assertEqual(saved_state["episodes"]["guid-1"]["season_number"], 2)
            self.assertEqual(saved_state["episodes"]["guid-1"]["episode_type"], "full")
            self.assertEqual(saved_state["episodes"]["guid-1"]["duration_seconds"], 3723)
            download_media.assert_not_called()
            transcode.assert_not_called()

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

    def test_available_episode_records_filters_missing_files(self) -> None:
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
            existing_path = config.public_episodes_dir / "guid-1.mp3"
            existing_path.parent.mkdir(parents=True, exist_ok=True)
            existing_path.write_bytes(b"audio")
            records = [
                {
                    "guid": "guid-1",
                    "title": "Available episode",
                    "processed_file": "guid-1.mp3",
                },
                {
                    "guid": "guid-2",
                    "title": "Missing episode",
                    "processed_file": "guid-2.mp3",
                },
            ]

            with self.assertLogs("podcast_proxy.service", level="WARNING") as captured:
                available = _available_episode_records(config, records)

            self.assertEqual(len(available), 1)
            self.assertEqual(available[0]["guid"], "guid-1")
            self.assertEqual(available[0]["enclosure_length"], 5)
            self.assertIn("omitting episode from losse-eindjes feed", captured.output[0])

    def test_drop_unavailable_episode_state_removes_missing_episode(self) -> None:
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
            episode_state = {
                "guid-1": {
                    "guid": "guid-1",
                    "processed_file": "guid-1.mp3",
                    "public_media_file": "media-change-me/losse-eindjes/episodes/guid-1.mp3",
                }
            }

            with self.assertLogs("podcast_proxy.service", level="WARNING") as captured:
                changed = _drop_unavailable_episode_state(config, episode_state)

            self.assertTrue(changed)
            self.assertEqual(episode_state, {})
            self.assertIn("dropping losse-eindjes state because published file is missing", captured.output[0])


if __name__ == "__main__":
    unittest.main()
