from __future__ import annotations

from html import escape, unescape
from pathlib import Path
import re
from typing import Any

from .config import AppConfig, PodcastConfig


def write_podcast_index(
    config: PodcastConfig,
    metadata: dict[str, Any],
    episode_records: list[dict[str, Any]],
) -> Path:
    title = escape(str(metadata.get("title", "Podcast Proxy")))
    description = escape(_plain_text(metadata.get("description", "")))
    image_url = metadata.get("image_url")
    feed_url = "feed.xml"

    image_markup = ""
    if image_url:
        image_markup = (
            f'<img class="cover" src="{escape(_relative_podcast_image_url(str(image_url)))}" alt="{title} cover art">'
        )
    mode_badge = _mode_badge(_resolved_mode_label(metadata), "mode-badge-hero")

    items_markup = "\n".join(
        _episode_card(record, fallback_image_url=image_url)
        for record in episode_records[:10]
    )
    if not items_markup:
        items_markup = "<p class=\"empty\">No episodes published yet.</p>"

    home_href = "../" if not config.legacy_root else "./"
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="alternate" type="application/rss+xml" title="{title}" href="{escape(feed_url)}">
  <style>{_shared_css()}</style>
</head>
<body>
  <main>
    <section class="hero">
      {mode_badge}
      <div>{image_markup}</div>
      <div>
        <p class="eyebrow"><a href="{escape(home_href)}">Podfixed:</a></p>
        <h1>{title}</h1>
        <p class="lede">{description}</p>
        <div class="actions">
          <a class="button rss-button" href="{escape(feed_url)}" aria-label="Open RSS feed">
            <span class="rss-icon" aria-hidden="true">{_rss_icon()}</span>
            <span>Open RSS</span>
          </a>
          <button class="link copy-feed" type="button" data-feed-url="{escape(feed_url)}" aria-label="Copy RSS feed URL">
            <span class="rss-icon" aria-hidden="true">{_rss_icon()}</span>
            <span>Copy RSS Link</span>
          </button>
        </div>
        <p class="hint">Click"Copy RSS Link" to copy the URL and paste it in your favorite podcast app.
        You can also open the RSS directly, or click on "Play" on any of the episodes below to listen directly.</p>
      </div>
    </section>
    <section>
      <h2>Recent Episodes</h2>
      <div class="episodes">
        {items_markup}
      </div>
    </section>
  </main>
</body>
<script>{_copy_script()}</script>
</html>
"""
    destination = config.public_index
    destination.write_text(html, encoding="utf-8")
    return destination


def write_library_index(app_config: AppConfig, podcasts: list[dict[str, Any]]) -> Path:
    cards = "\n".join(_podcast_card(card) for card in podcasts)
    if not cards:
        cards = "<p class=\"empty\">No podcasts configured yet.</p>"

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Podfix Library</title>
  <style>{_shared_css()}</style>
</head>
<body>
  <main>
    <section class="hero hero-library">
      <div>
        <h1>Podfix Library</h1>
        <p class="lede">Below is a list of podcasts which are post-processed so that speech is
        clear and of equal level between speakers as much as possible. The bitrate is also reduced
        to a more storage- and network friendly size. Click on "Open show page"
        for details per show, or use the "Copy RSS Link" to add the link to your favourite podcast
        app. Please remember to support the autors of the podcasts below by subscribing to their
        affeliate programs (Podimo, Patreon, Soundcloud, or socials).</p>
      </div>
    </section>
    <section>
      <h2>Available Podcasts</h2>
      <div class="podcasts">
        {cards}
      </div>
    </section>
  </main>
</body>
<script>{_copy_script()}</script>
</html>
"""
    destination = app_config.public_index
    destination.write_text(html, encoding="utf-8")
    return destination


def _episode_card(
    record: dict[str, Any],
    *,
    fallback_image_url: str | None,
) -> str:
    title = escape(str(record.get("title", "Untitled episode")))
    published = escape(str(record.get("published", "")))
    enclosure_url = escape(_relative_episode_url(str(record.get("enclosure_url", "#"))))
    image_url = str(record.get("image_url") or fallback_image_url or "")
    image_markup = ""
    if image_url:
        image_markup = (
            f'<img class="episode-image" src="{escape(_relative_podcast_image_url(image_url))}" alt="{title} artwork">'
        )
    return (
        "<article class=\"episode\">"
        f"{image_markup}"
        "<div class=\"episode-copy\">"
        f"<h3 class=\"episode-title\">{title}</h3>"
        f"<div class=\"meta\">{published}</div>"
        "</div>"
        f"<a class=\"audio play-button\" href=\"{enclosure_url}\" aria-label=\"Play processed MP3\">"
        "<span class=\"play-icon\" aria-hidden=\"true\">&#9654;</span>"
        "<span>Play</span>"
        "</a>"
        "</article>"
    )


def _podcast_card(card: dict[str, Any]) -> str:
    title = escape(str(card.get("title", "Untitled podcast")))
    description = escape(_plain_text(card.get("description", "")))
    slug = str(card.get("slug", "")).strip("/")
    feed_url = escape(f"{slug}/feed.xml" if slug else "feed.xml")
    index_url = escape(f"{slug}/index.html" if slug else "index.html")
    image_url = card.get("image_url")
    episodes = int(card.get("episode_count", 0))
    mode_badge = _mode_badge(_resolved_mode_label(card), "mode-badge-card")
    image_markup = ""
    if image_url:
        image_markup = (
            f'<img class="podcast-cover" src="{escape(f"{slug}/images/{Path(str(image_url)).name}" if slug else str(image_url))}" alt="{title} cover art">'
        )
    return (
        "<article class=\"podcast-card\">"
        f"{mode_badge}"
        f"{image_markup}"
        "<div class=\"podcast-copy\">"
        f"<h3 class=\"podcast-title\"><a href=\"{index_url}\">{title}</a></h3>"
        f"<p class=\"lede lede-small\">{description}</p>"
        f"<p class=\"meta\">{episodes} published episode{'s' if episodes != 1 else ''}</p>"
        "<div class=\"actions\">"
        f"<a class=\"button\" href=\"{index_url}\">Open show page</a>"
        f"<button class=\"link copy-feed\" type=\"button\" data-feed-url=\"{feed_url}\" aria-label=\"Copy RSS feed URL\"><span class=\"rss-icon\" aria-hidden=\"true\">{_rss_icon()}</span><span>Copy RSS Link</span></button>"
        "</div>"
        "</div>"
        "</article>"
    )


def _plain_text(value: Any) -> str:
    text = unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _resolved_mode_label(data: dict[str, Any]) -> str:
    mode = str(data.get("resolved_mode") or data.get("podcast_mode") or "").strip().lower()
    if mode == "story":
        return "Series"
    if mode == "news":
        return "News"
    return "Podcast"


def _mode_badge(label: str, extra_class: str) -> str:
    variant = {
        "Series": "mode-badge-series",
        "News": "mode-badge-news",
    }.get(label, "mode-badge-default")
    return f'<span class="mode-badge {escape(extra_class)} {variant}">{escape(label)}</span>'


def _shared_css() -> str:
    return """
    :root {
      --bg: #f6f4ef;
      --card: #fffdf7;
      --ink: #1f1b16;
      --muted: ##afadab;
      --accent: #0c63ff;
      --accent-ink: #ffffff;
      --line: rgba(31, 27, 22, 0.08);
      --shadow: 0 24px 60px rgba(31, 27, 22, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at top left, rgba(12, 99, 255, 0.12), transparent 30%),
        linear-gradient(180deg, #f8f6f1 0%, #f2ede4 100%);
      color: var(--ink);
      font-family: "Avenir Next", Avenir, "Segoe UI", Helvetica, Arial, sans-serif;
    }
    main {
      max-width: 980px;
      margin: 0 auto;
      padding: 40px 20px 64px;
    }
    .hero {
      display: grid;
      grid-template-columns: minmax(0, 280px) minmax(0, 1fr);
      gap: 28px;
      align-items: center;
      position: relative;
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 24px;
      box-shadow: var(--shadow);
    }
    .hero-library {
      grid-template-columns: 1fr;
    }
    .cover, .podcast-cover {
      width: 100%;
      display: block;
      border-radius: 22px;
    }
    .mode-badge {
      position: absolute;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 1px;
      padding: 1px 5px;
      border-radius: 999px;
      color: #3f3a34;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      backdrop-filter: blur(8px);
    }
    .mode-badge-news {
      background: rgba(246, 208, 118, 0.72);
      border: 1px solid rgba(190, 145, 31, 0.28);
    }
    .mode-badge-series {
      background: rgba(167, 214, 181, 0.78);
      border: 1px solid rgba(74, 130, 91, 0.26);
    }
    .mode-badge-default {
      background: rgba(31, 27, 22, 0.08);
      border: 1px solid rgba(31, 27, 22, 0.12);
    }
    .mode-badge-hero {
      top: 24px;
      right: 24px;
    }
    .mode-badge-card {
      top: 4px;
      right: 0;
    }
    h1 {
      margin: 0 0 12px;
      font-size: clamp(2rem, 5vw, 4rem);
      line-height: 0.95;
      letter-spacing: -0.04em;
    }
    h2 {
      margin: 0 0 16px;
      font-size: 1.3rem;
      letter-spacing: -0.03em;
    }
    .eyebrow {
      margin: 0 0 10px;
      font-size: 0.82rem;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--muted);
    }
    .eyebrow a {
      color: inherit;
      text-decoration: none;
    }
    .lede {
      margin: 0 0 18px;
      color: var(--muted);
      line-height: 1.55;
      font-size: 1.02rem;
    }
    .lede-small {
      font-size: 0.96rem;
      margin-bottom: 12px;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 20px 0 10px;
    }
    .button, .link {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 40px;
      padding: 0 15px;
      border-radius: 999px;
      text-decoration: none;
      font-weight: 700;
      gap: 10px;
      cursor: pointer;
      font: inherit;
    }
    .button {
      background: var(--accent);
      color: var(--accent-ink);
    }
    .link {
      color: var(--ink);
      border: 1px solid var(--line);
      background: rgb(246 208 118 / 60%);
    }
    button.link {
      appearance: none;
      -webkit-appearance: none;
    }
    .hint, .meta {
      margin: 0;
      color: var(--muted);
      font-size: 0.95rem;
    }
    section {
      margin-top: 30px;
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 22px;
      backdrop-filter: blur(10px);
    }
    .episodes {
      display: grid;
      gap: 14px;
    }
    .episode {
      display: grid;
      grid-template-columns: 72px minmax(0, 1fr) auto;
      gap: 14px;
      align-items: center;
      padding: 16px 0;
      border-top: 1px solid var(--line);
    }
    .episode:first-child { border-top: 0; padding-top: 0; }
    .episode-image {
      width: 72px;
      height: 72px;
      display: block;
      object-fit: cover;
      border-radius: 16px;
      box-shadow: 0 10px 24px rgba(31, 27, 22, 0.12);
    }
    .episode-copy {
      min-width: 0;
    }
    .episode-title, .podcast-title {
      margin: 0;
      font-size: 1.05rem;
      line-height: 1.3;
    }
    .audio, .podcast-title a {
      color: var(--accent);
      text-decoration: none;
      font-weight: 700;
    }
    .play-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 42px;
      padding: 0 16px;
      border-radius: 999px;
      border: 1px solid rgba(12, 99, 255, 0.18);
      background: rgba(12, 99, 255, 0.08);
      gap: 8px;
      white-space: nowrap;
    }
    .play-icon {
      display: inline-flex;
      width: 18px;
      height: 18px;
      align-items: center;
      justify-content: center;
      font-size: 0.9rem;
      line-height: 1;
    }
    .rss-icon {
      display: inline-flex;
      width: 18px;
      height: 18px;
      flex: 0 0 18px;
    }
    .rss-icon svg {
      width: 100%;
      height: 100%;
      display: block;
    }
    .podcasts {
      display: grid;
      gap: 18px;
    }
    .podcast-card {
      position: relative;
      display: grid;
      grid-template-columns: 160px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
      padding: 4px 0;
      border-top: 1px solid var(--line);
    }
    .podcast-card:first-child {
      border-top: 0;
      padding-top: 0;
    }
    .podcast-copy {
      padding: 0.5em;
      min-width: 0;
    }
    .empty {
      margin: 0;
      color: var(--muted);
    }
    @media (max-width: 760px) {
      .hero, .podcast-card {
        grid-template-columns: 1fr;
      }
      .mode-badge {
        right: 16px;
        min-width: 1px;
        padding: 1px 5px;
      }
      .mode-badge-hero {
        top: 16px;
      }
      .mode-badge-card {
        top: 0;
      }
      .episode {
        grid-template-columns: 56px minmax(0, 1fr);
        align-items: start;
      }
      .episode-image {
        width: 56px;
        height: 56px;
        border-radius: 12px;
      }
      .play-button {
        grid-column: 2;
      }
      main {
        padding: 20px 14px 40px;
      }
    }
    """


def _relative_podcast_image_url(url: str) -> str:
    image_name = Path(url).name
    if image_name:
        return f"images/{image_name}"
    return url


def _relative_episode_url(url: str) -> str:
    name = Path(url).name
    if name:
        return f"episodes/{name}"
    return url


def _rss_icon() -> str:
    return (
        '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<circle cx="6" cy="18" r="2.2" fill="currentColor"/>'
        '<path d="M4 10.5C9.25 10.5 13.5 14.75 13.5 20" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/>'
        '<path d="M4 4C13.94 4 22 12.06 22 22" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"/>'
        "</svg>"
    )


def _copy_script() -> str:
    return """
    document.querySelectorAll('.copy-feed').forEach((button) => {
      button.addEventListener('click', async () => {
        const label = button.querySelector('span:last-child');
        const original = label ? label.textContent : 'Copy RSS Link';
        const target = button.dataset.feedUrl || 'feed.xml';
        const absolute = new URL(target, window.location.href).href;
        try {
          await navigator.clipboard.writeText(absolute);
          if (label) label.textContent = 'Copied';
          window.setTimeout(() => {
            if (label) label.textContent = original;
          }, 1200);
        } catch (_error) {
          window.prompt('Copy this feed URL:', absolute);
        }
      });
    });
    """
