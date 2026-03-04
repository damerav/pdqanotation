import io
from PIL import Image, ImageDraw, ImageFont

BADGE_R = 22  # radius — 44px diameter circle
FILL = (220, 38, 38)
TEXT_COLOR = (255, 255, 255)
FONT_SIZE = 20


def annotate_screenshot(
    img_bytes: bytes,
    links: list[dict],
    viewport: str = "desktop",
    bboxes: list[dict] | None = None,
) -> bytes:
    """Draw red circle badges on the screenshot at each link location."""
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    width, height = img.size

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", FONT_SIZE
        )
    except (IOError, OSError):
        font = ImageFont.load_default()

    if not links:
        return img_bytes

    # Build a lookup from href -> bbox center
    bbox_map: dict[str, tuple[float, float]] = {}
    if bboxes:
        for bb in bboxes:
            href = bb.get("href", "")
            if href and "center_x" in bb and "center_y" in bb:
                # First match wins (some hrefs appear multiple times)
                if href not in bbox_map:
                    bbox_map[href] = (bb["center_x"], bb["center_y"])

    n = len(links)
    for i, link in enumerate(links):
        url = link.get("url", link.get("href", ""))
        letter = link.get("letter", "")
        if not letter:
            continue

        # Try to find bbox match
        cx, cy = None, None
        if url in bbox_map:
            cx, cy = bbox_map[url]
        else:
            # Fallback: right margin, evenly spaced
            cx = float(width - 30)
            cy = float((i + 1) * height / (n + 1))

        _draw_badge(draw, int(cx), int(cy), letter, font)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _draw_badge(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, letter: str, font
) -> None:
    """Draw a filled red circle with a white letter centered inside."""
    r = BADGE_R
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=FILL)
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2), letter, fill=TEXT_COLOR, font=font)
