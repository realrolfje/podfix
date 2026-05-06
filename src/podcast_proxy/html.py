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
        for record in episode_records
    )
    if not items_markup:
        items_markup = "<p class=\"empty\">No episodes published yet.</p>"

    home_href = "../"
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
    <p class="eyebrow"><a href="{escape(home_href)}">&larr; All shows</a></p>
    <section class="hero">
      {mode_badge}
      <div>{image_markup}</div>
      <div>
        <h1>{title}</h1>
        <p class="lede">{description}</p>
        <div class="actions">
          <button class="link copy-feed" type="button" data-feed-url="{escape(feed_url)}" aria-label="Copy RSS feed URL">
            <span class="rss-icon" aria-hidden="true">{_rss_icon()}</span>
            <span>Copy RSS Link</span>
          </button>
        </div>
        <p class="hint apple-hint">Apple Podcasts: copy the RSS link, then use "Follow a Show by URL" on iPhone or iPad, or "Add a Show by URL..." on Mac.</p>
        <div class="search-panel search-panel-hero">
          <label class="search-label" for="episode-search">Find an episode</label>
          <input id="episode-search" class="search-input" type="search" placeholder="Type to filter episodes by title or date" autocomplete="off">
          <p id="episode-search-status" class="search-status" aria-live="polite"></p>
        </div>
      </div>
    </section>
    <section>
      <h2>Recent Episodes</h2>
      <p id="episode-search-empty" class="empty search-empty" aria-live="polite"></p>
      <div class="episodes" id="episode-list">
        {items_markup}
      </div>
    </section>
    {_podfix_footer()}
  </main>
<script>{_copy_script()}</script>
</body>
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
        <h1>Your Podfix Library</h1>
        <p class="lede">Below are your podcasts, post-processed so that speech is
        clear and of equal level between speakers as much as possible. Click on the show image 
        for details per show, or use the "Copy RSS Link" to add the link to your favourite podcast
        app. Please remember to support the autors of the podcasts below by subscribing to their
        affeliate programs (Podimo, Patreon, Soundcloud, or socials).</p>
        <p class="hint apple-hint">Using Apple Podcasts? Open a show, copy its RSS link, then add it in Podcasts with "Follow a Show by URL" on iPhone or iPad, or "Add a Show by URL..." on Mac.</p>
        <div class="search-panel search-panel-hero">
          <label class="search-label" for="podcast-search">Find a show</label>
          <input id="podcast-search" class="search-input" type="search" placeholder="Type to filter podcasts by title or description" autocomplete="off">
          <p id="podcast-search-status" class="search-status" aria-live="polite"></p>
        </div>
      </div>
    </section>
    <section>
      <h2>Available Podcasts</h2>
      <p id="podcast-search-empty" class="empty search-empty" aria-live="polite"></p>
      <div class="podcasts" id="podcast-list">
        {cards}
      </div>
    </section>
    {_podfix_footer()}
  </main>
<script>{_copy_script()}</script>
</body>
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
    raw_title = str(record.get("title", "Untitled episode"))
    raw_published = str(record.get("published", ""))
    title = escape(raw_title)
    published = escape(raw_published)
    enclosure_url = escape(_relative_episode_url(str(record.get("enclosure_url", "#"))))
    image_url = str(record.get("image_url") or fallback_image_url or "")
    episode_meta = _episode_meta_label(record)
    duration_label = _duration_label(record.get("duration_seconds"))
    meta_parts: list[str] = []
    if episode_meta:
        meta_parts.append(f'<span class="meta-chip">{escape(episode_meta)}</span>')
    if published:
        meta_parts.append(f'<span class="meta-date">{published}</span>')
    meta_markup = " ".join(meta_parts)
    search_text = escape(
        " ".join(
            part for part in (raw_title, raw_published, episode_meta or "", duration_label or "") if part
        ).casefold()
    )
    image_markup = ""
    if image_url:
        image_markup = (
            f'<img class="episode-image" src="{escape(_relative_podcast_image_url(image_url))}" alt="{title} artwork">'
        )
    return (
        f"<article class=\"episode\" data-search-text=\"{search_text}\">"
        f"{image_markup}"
        "<div class=\"episode-copy\">"
        f"<h3 class=\"episode-title\">{title}</h3>"
        f"<div class=\"meta\">{meta_markup}</div>"
        "</div>"
        f"<a class=\"audio play-button\" href=\"{enclosure_url}\" aria-label=\"Play processed MP3\">"
        "<span class=\"play-icon\" aria-hidden=\"true\">&#9654;</span>"
        f"<span>{escape(_play_button_label(duration_label))}</span>"
        "</a>"
        "</article>"
    )


def _podcast_card(card: dict[str, Any]) -> str:
    raw_title = str(card.get("title", "Untitled podcast"))
    raw_description = _plain_text(card.get("description", ""))
    raw_slug = str(card.get("slug", "")).strip("/")
    title = escape(raw_title)
    description = escape(raw_description)
    slug = str(card.get("slug", "")).strip("/")
    feed_url = escape(f"{slug}/feed.xml" if slug else "feed.xml")
    index_url = escape(f"{slug}/index.html" if slug else "index.html")
    image_url = card.get("image_url")
    episodes = int(card.get("episode_count", 0))
    mode_badge = _mode_badge(_resolved_mode_label(card), "mode-badge-card")
    search_text = escape(" ".join(part for part in (raw_title, raw_description, raw_slug) if part).casefold())
    image_markup = ""
    if image_url:
        image_markup = (
            f'<a class="podcast-cover-link" href="{index_url}" aria-label="Open {title} show page">'
            f'<img class="podcast-cover" src="{escape(f"{slug}/images/{Path(str(image_url)).name}" if slug else str(image_url))}" alt="{title} cover art">'
            "</a>"
        )
    return (
        f"<article class=\"podcast-card\" data-search-text=\"{search_text}\">"
        f"{mode_badge}"
        f"{image_markup}"
        "<div class=\"podcast-copy\">"
        f"<h3 class=\"podcast-title\"><a href=\"{index_url}\">{title}</a></h3>"
        f"<p class=\"lede lede-small\">{description}</p>"
        f"<p class=\"meta\">{episodes} published episode{'s' if episodes != 1 else ''}</p>"
        "<div class=\"actions\">"
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


def _episode_meta_label(record: dict[str, Any]) -> str | None:
    season = _optional_int(record.get("season_number"))
    episode = _optional_int(record.get("episode_number"))
    if season is not None and episode is not None:
        return f"S{season} E{episode}"
    if episode is not None:
        return f"Episode {episode}"
    if season is not None:
        return f"Season {season}"
    return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _duration_label(value: Any) -> str | None:
    seconds = _optional_int(value)
    if seconds is None or seconds < 0:
        return None
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _play_button_label(duration_label: str | None) -> str:
    if duration_label:
        return f"Play {duration_label}"
    return "Play"


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


def _podfix_footer() -> str:
    return (
        '<footer class="site-footer">'
        'Made with <a href="https://www.rolfje.com/2026/04/01/the-podcast-problem-fixed/">Podfix</a>.'
        "</footer>"
    )


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
      padding: 24px 20px 40px;
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
      padding: 20px;
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
    .podcast-cover-link {
      display: block;
      border-radius: 22px;
    }
    .podcast-cover-link:focus-visible {
      outline: 3px solid rgba(12, 99, 255, 0.35);
      outline-offset: 4px;
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
      margin: 0 0 14px;
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
      margin: 16px 0 8px;
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
    .apple-hint {
      margin-top: 8px;
    }
    section {
      margin-top: 18px;
      background: rgba(255, 255, 255, 0.72);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 18px;
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
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
      align-items: center;
    }
    .meta-chip {
      display: inline-flex;
      align-items: center;
      min-height: 26px;
      padding: 0 10px;
      border-radius: 999px;
      background: rgba(12, 99, 255, 0.1);
      color: #0b4cc7;
      font-size: 0.83rem;
      font-weight: 700;
      letter-spacing: 0.01em;
    }
    .meta-date {
      white-space: nowrap;
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
      gap: 12px;
    }
    .search-panel {
      display: grid;
      gap: 10px;
    }
    .search-panel-hero {
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--line);
    }
    .search-label {
      font-size: 0.84rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #5b554d;
    }
    .search-input {
      width: 100%;
      min-height: 52px;
      padding: 0 18px;
      border: 1px solid rgba(31, 27, 22, 0.12);
      border-radius: 16px;
      background: rgba(255, 253, 247, 0.92);
      color: var(--ink);
      font: inherit;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.65);
    }
    .search-input:focus {
      outline: 2px solid rgba(12, 99, 255, 0.22);
      outline-offset: 2px;
      border-color: rgba(12, 99, 255, 0.38);
    }
    .search-status {
      margin: 0;
      color: var(--muted);
      font-size: 0.95rem;
      display: none;
    }
    .podcast-card {
      position: relative;
      display: grid;
      grid-template-columns: 160px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
      padding: 2px 0;
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
    .site-footer {
      margin: 22px 0 0;
      color: var(--muted);
      font-size: 0.9rem;
      text-align: center;
    }
    .site-footer a {
      color: inherit;
      font-weight: 700;
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }
    .search-empty {
      display: none;
      margin-bottom: 12px;
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
    (function () {
      var buttons = document.querySelectorAll('.copy-feed');
      Array.prototype.forEach.call(buttons, function (button) {
        button.addEventListener('click', function () {
          var label = button.querySelector('span:last-child');
          var original = label ? label.textContent : 'Copy RSS Link';
          var target = button.getAttribute('data-feed-url') || 'feed.xml';
          var absolute = new URL(target, window.location.href).href;

          var setCopiedLabel = function () {
            if (!label) return;
            label.textContent = 'Copied';
            window.setTimeout(function () {
              label.textContent = original;
            }, 1200);
          };

          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(absolute).then(setCopiedLabel).catch(function () {
              window.prompt('Copy this feed URL:', absolute);
            });
            return;
          }

          window.prompt('Copy this feed URL:', absolute);
        });
      });

      var wireSearch = function (inputId, statusId, emptyId, selector, singularLabel, pluralLabel) {
        var searchInput = document.getElementById(inputId);
        var searchStatus = document.getElementById(statusId);
        var emptyState = document.getElementById(emptyId);
        var cards = document.querySelectorAll(selector);

        if (!searchInput || !searchStatus || !emptyState || !cards.length) {
          return;
        }

        var updateSearch = function () {
          var query = String(searchInput.value || '').replace(/^\\s+|\\s+$/g, '').toLowerCase();
          var visibleCount = 0;

          Array.prototype.forEach.call(cards, function (card) {
            var haystack = String(card.getAttribute('data-search-text') || '').toLowerCase();
            var matches = !query || haystack.indexOf(query) !== -1;
            card.style.display = matches ? '' : 'none';
            if (matches) {
              visibleCount += 1;
            }
          });

          if (!query) {
            searchStatus.textContent = '';
            searchStatus.style.display = 'none';
            emptyState.textContent = '';
            emptyState.style.display = 'none';
          } else if (visibleCount === 0) {
            searchStatus.textContent = '';
            searchStatus.style.display = 'none';
            emptyState.textContent = 'No ' + pluralLabel + ' match "' + query + '".';
            emptyState.style.display = 'block';
          } else if (visibleCount === 1) {
            searchStatus.textContent = '';
            searchStatus.style.display = 'none';
            emptyState.textContent = '';
            emptyState.style.display = 'none';
          } else {
            searchStatus.textContent = '';
            searchStatus.style.display = 'none';
            emptyState.textContent = '';
            emptyState.style.display = 'none';
          }
        };

        searchInput.addEventListener('input', updateSearch);
        updateSearch();
      };

      wireSearch('podcast-search', 'podcast-search-status', 'podcast-search-empty', '.podcast-card', 'podcast', 'podcasts');
      wireSearch('episode-search', 'episode-search-status', 'episode-search-empty', '.episode', 'episode', 'episodes');
    }());
    """
