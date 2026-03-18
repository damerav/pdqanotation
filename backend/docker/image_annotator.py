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

    # Build a lookup from href -> list of (center_x, center_y, right_x, text)
    bbox_by_href: dict[str, list[dict]] = {}
    if bboxes:
        for bb in bboxes:
            href = bb.get("href", "")
            if href and "center_x" in bb and "center_y" in bb:
                bbox_by_href.setdefault(href, []).append(bb)

    # Offset from the link's right edge to the badge center
    badge_gap = BADGE_R + 10

    # Track which bboxes have been used so duplicate URLs get different badges
    used_bboxes: set[int] = set()

    n = len(links)
    for i, link in enumerate(links):
        url = link.get("url", link.get("href", ""))
        anchor = link.get("anchor_text", link.get("label", "")).strip().lower()
        letter = link.get("letter", "")
        if not letter:
            continue

        candidates = bbox_by_href.get(url, [])
        best_bb = None

        if candidates:
            # Try to match by anchor text first (handles duplicate URLs)
            for j, bb in enumerate(candidates):
                bb_id = id(bb)
                if bb_id in used_bboxes:
                    continue
                bb_text = bb.get("text", "").strip().lower()
                if anchor and bb_text and anchor in bb_text or bb_text in anchor:
                    best_bb = bb
                    used_bboxes.add(bb_id)
                    break

            # If no text match, use the first unused bbox for this URL
            if best_bb is None:
                for bb in candidates:
                    bb_id = id(bb)
                    if bb_id not in used_bboxes:
                        best_bb = bb
                        used_bboxes.add(bb_id)
                        break

            # Last resort: reuse the first bbox
            if best_bb is None and candidates:
                best_bb = candidates[0]

        if best_bb:
            cy = best_bb["center_y"]
            right_x = best_bb.get("right_x")
            if right_x is not None:
                cx = min(right_x + badge_gap, width - BADGE_R - 2)
            else:
                content_right = (width + 600) / 2
                cx = min(content_right + badge_gap, width - BADGE_R - 2)
        else:
            cx = float(width - BADGE_R - 8)
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
