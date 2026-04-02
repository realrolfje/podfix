from __future__ import annotations

import base64
from pathlib import Path
import tempfile
import unittest

from podcast_proxy.cli import _is_authorized, _parse_range_header
from podcast_proxy.config import load_config


class ServeAuthTests(unittest.TestCase):
    def test_load_config_uses_default_basic_auth_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "config.toml"
            config_path.write_text(
                '\n'.join(
                    [
                        'base_url = "http://localhost:8080"',
                        f'output_dir = "{root / "output"}"',
                        "",
                        "[[podcasts]]",
                        'slug = "example"',
                        'upstream_feed_url = "https://example.com/feed.xml"',
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(config_path)

        self.assertEqual(config.podcasts[0].http.basic_auth_username, "podfix")
        self.assertEqual(config.podcasts[0].http.basic_auth_password, "change-me")

    def test_is_authorized_rejects_missing_or_invalid_headers(self) -> None:
        self.assertFalse(
            _is_authorized(
                None,
                username="podfix",
                password="change-me",
            )
        )
        self.assertFalse(
            _is_authorized(
                "Bearer token",
                username="podfix",
                password="change-me",
            )
        )
        self.assertFalse(
            _is_authorized(
                "Basic not-base64",
                username="podfix",
                password="change-me",
            )
        )
        self.assertFalse(
            _is_authorized(
                f"Basic {base64.b64encode(b'podfix:wrong').decode('ascii')}",
                username="podfix",
                password="change-me",
            )
        )

    def test_is_authorized_accepts_matching_basic_auth_header(self) -> None:
        self.assertTrue(
            _is_authorized(
                f"Basic {base64.b64encode(b'podfix:change-me').decode('ascii')}",
                username="podfix",
                password="change-me",
            )
        )

    def test_parse_range_header_accepts_standard_and_suffix_ranges(self) -> None:
        self.assertEqual(_parse_range_header("bytes=0-1", 100), (0, 1))
        self.assertEqual(_parse_range_header("bytes=10-", 100), (10, 99))
        self.assertEqual(_parse_range_header("bytes=-10", 100), (90, 99))
        self.assertEqual(_parse_range_header("bytes=-200", 100), (0, 99))

    def test_parse_range_header_rejects_invalid_ranges(self) -> None:
        self.assertIsNone(_parse_range_header(None, 100))
        self.assertIsNone(_parse_range_header("items=0-1", 100))
        self.assertIsNone(_parse_range_header("bytes=5-1", 100))
        self.assertIsNone(_parse_range_header("bytes=100-101", 100))
        self.assertIsNone(_parse_range_header("bytes=0-1,4-5", 100))


if __name__ == "__main__":
    unittest.main()
