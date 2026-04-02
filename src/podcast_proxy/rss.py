from __future__ import annotations

from typing import Any
import xml.etree.ElementTree as ET

from .config import PodcastConfig


ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


def write_feed(
    config: PodcastConfig,
    metadata: dict[str, Any],
    episode_records: list[dict[str, Any]],
) -> Path:
    ET.register_namespace("itunes", ITUNES_NS)
    ET.register_namespace("content", CONTENT_NS)

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    _text(channel, "title", metadata.get("title", "Podcast Proxy"))
    _text(channel, "link", metadata.get("link") or config.public_base_url)
    _text(channel, "description", metadata.get("description", ""))
    _text(channel, "language", metadata.get("language"))
    _text(channel, f"{{{ITUNES_NS}}}author", metadata.get("author"))
    _text(channel, f"{{{ITUNES_NS}}}summary", metadata.get("description", ""))
    _text(channel, f"{{{ITUNES_NS}}}explicit", metadata.get("explicit"))
    _text(channel, f"{{{ITUNES_NS}}}type", _itunes_type(metadata))
    category_text = _itunes_category_text(metadata.get("category"))
    if category_text:
        category = ET.SubElement(channel, f"{{{ITUNES_NS}}}category")
        category.set("text", category_text)
    if metadata.get("image_url"):
        image = ET.SubElement(channel, "image")
        _text(image, "url", metadata["image_url"])
        _text(image, "title", metadata.get("title", "Podcast Proxy"))
        _text(image, "link", metadata.get("link") or config.public_base_url)
        itunes_image = ET.SubElement(channel, f"{{{ITUNES_NS}}}image")
        itunes_image.set("href", str(metadata["image_url"]))

    for record in episode_records:
        item = ET.SubElement(channel, "item")
        _text(item, "title", record["title"])
        _text(item, "description", record["description"])
        _text(item, f"{{{CONTENT_NS}}}encoded", record["description"])
        _text(item, "pubDate", record["published"])
        _text(item, "guid", record["guid"])
        if record.get("author"):
            _text(item, f"{{{ITUNES_NS}}}author", record["author"])
        _text(item, f"{{{ITUNES_NS}}}explicit", record.get("explicit", "false"))
        if record.get("original_link"):
            _text(item, "link", record["original_link"])
        if record.get("image_url"):
            item_image = ET.SubElement(item, f"{{{ITUNES_NS}}}image")
            item_image.set("href", str(record["image_url"]))
        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", record["enclosure_url"])
        enclosure.set("length", str(record["enclosure_length"]))
        enclosure.set("type", "audio/mpeg")

    tree = ET.ElementTree(rss)
    config.public_feed.parent.mkdir(parents=True, exist_ok=True)
    tree.write(config.public_feed, encoding="utf-8", xml_declaration=True)
    return config.public_feed


def _text(parent: ET.Element, tag: str, value: Any) -> None:
    if value is None:
        return
    element = ET.SubElement(parent, tag)
    element.text = str(value)


def _itunes_type(metadata: dict[str, Any]) -> str | None:
    feed_type = str(metadata.get("itunes_type") or "").strip().lower()
    if feed_type in {"serial", "episodic"}:
        return feed_type
    resolved_mode = str(metadata.get("resolved_mode") or "").strip().lower()
    if resolved_mode == "story":
        return "serial"
    if resolved_mode == "news":
        return "episodic"
    return None


def _itunes_category_text(value: Any) -> str | None:
    category = str(value or "").strip()
    if not category:
        return None
    if category.isdigit():
        return None
    return category
