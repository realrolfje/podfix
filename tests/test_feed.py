from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from podcast_proxy.config import FFMpegConfig, HTTPConfig, PodcastConfig
from podcast_proxy.feed import (
    _entry_to_episode,
    _parse_duration_seconds,
    _normalize_episode_type,
    _normalize_explicit,
    _parse_optional_int,
)
from podcast_proxy.rss import ITUNES_NS, _itunes_category_text, write_feed


class ExplicitNormalizationTests(unittest.TestCase):
    def test_normalize_explicit_defaults_to_false(self) -> None:
        self.assertEqual(_normalize_explicit(None), "false")
        self.assertEqual(_normalize_explicit(""), "false")
        self.assertEqual(_normalize_explicit("unknown"), "false")

    def test_normalize_explicit_preserves_true_values(self) -> None:
        self.assertEqual(_normalize_explicit("yes"), "true")
        self.assertEqual(_normalize_explicit("true"), "true")
        self.assertEqual(_normalize_explicit("explicit"), "true")

    def test_normalize_explicit_preserves_false_values(self) -> None:
        self.assertEqual(_normalize_explicit("no"), "false")
        self.assertEqual(_normalize_explicit("false"), "false")
        self.assertEqual(_normalize_explicit("clean"), "false")


class AppleMetadataParsingTests(unittest.TestCase):
    def test_parse_optional_int_accepts_valid_numbers(self) -> None:
        self.assertEqual(_parse_optional_int("7"), 7)
        self.assertEqual(_parse_optional_int(3), 3)
        self.assertIsNone(_parse_optional_int(""))
        self.assertIsNone(_parse_optional_int("abc"))

    def test_normalize_episode_type_keeps_known_values(self) -> None:
        self.assertEqual(_normalize_episode_type("full"), "full")
        self.assertEqual(_normalize_episode_type("Trailer"), "trailer")
        self.assertIsNone(_normalize_episode_type("preview"))

    def test_parse_duration_seconds_accepts_itunes_formats(self) -> None:
        self.assertEqual(_parse_duration_seconds("42"), 42)
        self.assertEqual(_parse_duration_seconds("03:15"), 195)
        self.assertEqual(_parse_duration_seconds("1:02:03"), 3723)
        self.assertIsNone(_parse_duration_seconds("abc"))

    def test_entry_to_episode_preserves_itunes_episode_fields(self) -> None:
        class EntryFixture(dict):
            def __getattr__(self, name: str) -> object:
                return self[name]

        entry = EntryFixture(
            {
                "id": "episode-guid",
                "title": "Episode 7",
                "published": "Thu, 11 Dec 2025 15:47:00 +0100",
                "enclosures": [
                    {"href": "https://example.com/audio.mp3", "type": "audio/mpeg"}
                ],
                "itunes_episode": "7",
                "itunes_season": "2",
                "itunes_episodetype": "full",
                "itunes_duration": "1:02:03",
            }
        )

        episode = _entry_to_episode(entry)

        self.assertEqual(episode.episode_number, 7)
        self.assertEqual(episode.season_number, 2)
        self.assertEqual(episode.episode_type, "full")
        self.assertEqual(episode.duration_seconds, 3723)


class ItunesCategoryTests(unittest.TestCase):
    def test_itunes_category_text_drops_numeric_values(self) -> None:
        self.assertIsNone(_itunes_category_text(None))
        self.assertIsNone(_itunes_category_text(""))
        self.assertIsNone(_itunes_category_text("650674"))

    def test_itunes_category_text_keeps_named_categories(self) -> None:
        self.assertEqual(_itunes_category_text("News"), "News")
        self.assertEqual(_itunes_category_text("Society & Culture"), "Society & Culture")


class RSSWritingTests(unittest.TestCase):
    def test_write_feed_emits_episode_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = PodcastConfig(
                slug="story-show",
                upstream_feed_url="https://example.com/feed.xml",
                episode_title_include=None,
                base_url="https://static.example.com/private/podfix/data/published",
                output_dir=Path(temp_dir),
                keep_original_downloads=False,
                cache_artwork=False,
                badge_artwork=False,
                max_episodes=None,
                podcast_mode="story",
                media_path_token="media-change-me",
                http=HTTPConfig(),
                ffmpeg=FFMpegConfig(),
            )
            config.ensure_directories()

            write_feed(
                config,
                {"title": "Story Show", "resolved_mode": "story"},
                [
                    {
                        "guid": "episode-guid",
                        "title": "Episode 7",
                        "description": "desc",
                        "published": "Thu, 11 Dec 2025 15:47:00 +0100",
                        "enclosure_url": "https://example.com/audio.mp3",
                        "enclosure_length": 123,
                        "explicit": "false",
                        "episode_number": 7,
                        "season_number": 2,
                        "episode_type": "full",
                    }
                ],
            )

            root = ET.fromstring(config.public_feed.read_text(encoding="utf-8"))
            item = root.find("./channel/item")
            self.assertIsNotNone(item)
            self.assertEqual(item.findtext(f"{{{ITUNES_NS}}}episode"), "7")
            self.assertEqual(item.findtext(f"{{{ITUNES_NS}}}season"), "2")
            self.assertEqual(item.findtext(f"{{{ITUNES_NS}}}episodeType"), "full")


if __name__ == "__main__":
    unittest.main()
