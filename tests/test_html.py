from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from podcast_proxy.config import FFMpegConfig, HTTPConfig, PodcastConfig
from podcast_proxy.html import write_podcast_index


class HtmlTests(unittest.TestCase):
    def test_write_podcast_index_renders_all_episode_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="olaf-zit-vast",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=False,
                badge_artwork=False,
                max_episodes=20,
                podcast_mode="news",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )
            config.ensure_directories()
            metadata = {
                "title": "Olaf zit vast",
                "description": "desc",
                "resolved_mode": "news",
            }
            episode_records = [
                {
                    "guid": f"guid-{index}",
                    "title": f"Episode {index}",
                    "description": "desc",
                    "published": f"Thu, {index:02d} Dec 2025 15:47:00 +0100",
                    "enclosure_url": f"https://example.com/{index}.mp3",
                    "enclosure_length": 123,
                    "enclosure_type": "audio/mpeg",
                }
                for index in range(1, 12)
            ]

            destination = write_podcast_index(config, metadata, episode_records)
            html = destination.read_text(encoding="utf-8")

        self.assertEqual(html.count('class="episode"'), 11)
        self.assertIn("Episode 11", html)


if __name__ == "__main__":
    unittest.main()
