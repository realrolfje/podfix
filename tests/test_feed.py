from __future__ import annotations

import unittest

from podcast_proxy.feed import _normalize_explicit
from podcast_proxy.rss import _itunes_category_text


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


class ItunesCategoryTests(unittest.TestCase):
    def test_itunes_category_text_drops_numeric_values(self) -> None:
        self.assertIsNone(_itunes_category_text(None))
        self.assertIsNone(_itunes_category_text(""))
        self.assertIsNone(_itunes_category_text("650674"))

    def test_itunes_category_text_keeps_named_categories(self) -> None:
        self.assertEqual(_itunes_category_text("News"), "News")
        self.assertEqual(_itunes_category_text("Society & Culture"), "Society & Culture")


if __name__ == "__main__":
    unittest.main()
