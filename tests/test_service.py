from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from podcast_proxy.config import FFMpegConfig, HTTPConfig, PodcastConfig
from podcast_proxy.feed import Episode
from podcast_proxy.service import _rebuild_episode_artwork


class RebuildImagesTests(unittest.TestCase):
    def test_rebuild_images_refreshes_enclosure_url_from_processed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="losse-eindjes",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.rolfje.com/private/podfix/data/public",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=False,
                badge_artwork=False,
                max_episodes=5,
                podcast_mode="news",
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
            )
            episode_state = {
                episode.guid: {
                    "guid": episode.guid,
                    "processed_file": "Thu-11-Dec-2025-15-47-00-0100-Nieuwe-Podcast-Losse-Eindjes-WO_KN_20309964.mp3",
                    "enclosure_url": "http://static.rolfje.com/private/podfix/data/public/losse-eindjes/episodes/Thu-11-Dec-2025-15-47-00-0100-Nieuwe-Podcast-Losse-Eindjes-WO_KN_20309964.mp3",
                    "image_url": None,
                }
            }

            rebuilt = _rebuild_episode_artwork(
                session=None,
                config=config,
                episodes=[episode],
                episode_state=episode_state,
                resolved_mode="news",
            )

        self.assertEqual(
            rebuilt[episode.guid]["enclosure_url"],
            "https://static.rolfje.com/private/podfix/data/public/losse-eindjes/episodes/Thu-11-Dec-2025-15-47-00-0100-Nieuwe-Podcast-Losse-Eindjes-WO_KN_20309964.mp3",
        )


if __name__ == "__main__":
    unittest.main()
