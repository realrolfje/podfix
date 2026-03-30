from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
import requests

from .config import PodcastConfig
from .utils import sha1_text


BADGE_TEXT = "COMPRESSED"
BADGE_COLOR = "#1F6BFF"
TEXT_COLOR = "#FFFFFF"
BADGE_BORDER = "#FFFFFF"
BADGE_SHADOW = (0, 0, 0, 80)
MAX_ARTWORK_SIZE = (200, 200)


def process_artwork(
    session: requests.Session,
    config: PodcastConfig,
    image_url: str,
) -> str:
    response = session.get(image_url, timeout=config.http.timeout_seconds)
    response.raise_for_status()
    extension = _extension_for_content_type(
        response.headers.get("Content-Type", "")
    ) or Path(image_url).suffix or ".png"
    filename = f"artwork-{sha1_text(image_url)}{extension}"
    destination = config.public_images_dir / filename

    image = Image.open(BytesIO(response.content)).convert("RGBA")
    image = _resize_for_public_artwork(image)
    badged = _add_badge(image)
    if extension.lower() in {".jpg", ".jpeg"}:
        badged.convert("RGB").save(destination, quality=85, optimize=True)
    else:
        badged.save(destination, optimize=True)
    return f"{config.public_base_url}/images/{filename}"


def _add_badge(image: Image.Image) -> Image.Image:
    width, height = image.size
    badge_height = max(36, int(height * 0.14))
    horizontal_padding = max(18, int(badge_height * 0.45))
    vertical_padding = max(10, int(badge_height * 0.22))

    font = _load_font(max(18, int(badge_height * 0.42)))
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), BADGE_TEXT, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    pill_width = text_width + horizontal_padding * 2
    pill_height = text_height + vertical_padding * 2
    margin = max(18, int(min(width, height) * 0.04))
    left = width - margin - pill_width
    top = margin
    right = width - margin
    bottom = top + pill_height
    radius = pill_height // 2

    shadow_offset = max(8, pill_height // 9)
    shadow_blur = max(12, pill_height // 4)
    shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    shadow_draw.rounded_rectangle(
        (
            left,
            top + shadow_offset,
            right,
            bottom + shadow_offset,
        ),
        radius=radius,
        fill=BADGE_SHADOW,
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
    image.alpha_composite(shadow_layer)

    draw.rounded_rectangle(
        (left, top, right, bottom),
        radius=radius,
        fill=BADGE_COLOR,
        outline=BADGE_BORDER,
        width=max(3, pill_height // 14),
    )
    text_x = left + (pill_width - text_width) / 2
    text_y = top + (pill_height - text_height) / 2 - 1
    draw.text(
        (text_x, text_y),
        BADGE_TEXT,
        fill=TEXT_COLOR,
        font=font,
        anchor="lt",
    )
    return image


def _resize_for_public_artwork(image: Image.Image) -> Image.Image:
    resized = image.copy()
    resized.thumbnail(MAX_ARTWORK_SIZE, Image.Resampling.LANCZOS)
    return resized


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial_Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        font_path = Path(path)
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size=size)
    return ImageFont.load_default()


def _extension_for_content_type(content_type: str) -> str | None:
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    return mapping.get(content_type.split(";")[0].strip().lower())
