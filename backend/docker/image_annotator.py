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
    fuzzy_match: bool = False,
) -> tuple[bytes, dict]:
    """Draw red circle badges on the screenshot at each link location.

    Returns (annotated_image_bytes, match_stats) where match_stats contains:
      - total: number of links with letters
      - matched: number placed using real bounding boxes
      - fallback: number placed at estimated positions
      - confidence: matched / total as a percentage (0-100)
    """
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
        return img_bytes, {"total": 0, "matched": 0, "fallback": 0, "confidence": 100}

    # Build a lookup from href -> list of bounding boxes
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
    matched_count = 0
    fallback_count = 0
    total_count = 0

    n = len(links)
    for i, link in enumerate(links):
        url = link.get("url", link.get("href", ""))
        anchor = link.get("anchor_text", link.get("label", "")).strip().lower()
        letter = link.get("letter", "")
        if not letter:
            continue

        total_count += 1
        candidates = bbox_by_href.get(url, [])

        # Fuzzy match: if no exact URL match, try partial URL matching
        if not candidates and fuzzy_match:
            candidates = _fuzzy_find_bbox(url, bbox_by_href)

        best_bb = _pick_best_bbox(candidates, anchor, used_bboxes)

        if best_bb:
            matched_count += 1
            cy = best_bb["center_y"]
            right_x = best_bb.get("right_x")
            if right_x is not None:
                cx = min(right_x + badge_gap, width - BADGE_R - 2)
            else:
                content_right = (width + 600) / 2
                cx = min(content_right + badge_gap, width - BADGE_R - 2)
        else:
            fallback_count += 1
            cx = float(width - BADGE_R - 8)
            cy = float((i + 1) * height / (n + 1))

        _draw_badge(draw, int(cx), int(cy), letter, font)

    confidence = round(matched_count / total_count * 100) if total_count > 0 else 100

    out = io.BytesIO()
    img.save(out, format="PNG")

    stats = {
        "total": total_count,
        "matched": matched_count,
        "fallback": fallback_count,
        "confidence": confidence,
    }
    return out.getvalue(), stats


def _pick_best_bbox(
    candidates: list[dict], anchor: str, used_bboxes: set[int]
) -> dict | None:
    """Pick the best bounding box from candidates, preferring text match."""
    if not candidates:
        return None

    # Try to match by anchor text first (handles duplicate URLs)
    for bb in candidates:
        bb_id = id(bb)
        if bb_id in used_bboxes:
            continue
        bb_text = bb.get("text", "").strip().lower()
        if anchor and bb_text and (anchor in bb_text or bb_text in anchor):
            used_bboxes.add(bb_id)
            return bb

    # If no text match, use the first unused bbox for this URL
    for bb in candidates:
        bb_id = id(bb)
        if bb_id not in used_bboxes:
            used_bboxes.add(bb_id)
            return bb

    # Last resort: reuse the first bbox
    return candidates[0] if candidates else None


def _fuzzy_find_bbox(
    url: str, bbox_by_href: dict[str, list[dict]]
) -> list[dict]:
    """Find bounding boxes using fuzzy URL matching.

    Handles cases where the HTML parser and Playwright see slightly different
    URLs (e.g., URL encoding differences, trailing slashes, query param order).
    """
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(url)
    path = parsed.path.rstrip("/").lower()

    for href, bbs in bbox_by_href.items():
        href_parsed = urlparse(href)
        href_path = href_parsed.path.rstrip("/").lower()

        # Same domain + path is a strong match
        if (parsed.netloc.lower() == href_parsed.netloc.lower()
                and path == href_path):
            return bbs

    # Try matching by the last path segment (common in tracking URLs)
    if path:
        last_seg = path.split("/")[-1]
        if len(last_seg) > 5:  # avoid matching on short generic segments
            for href, bbs in bbox_by_href.items():
                if last_seg in href.lower():
                    return bbs

    return []


def _draw_badge(
    draw: ImageDraw.ImageDraw, cx: int, cy: int, letter: str, font
) -> None:
    """Draw a filled red circle with a white letter centered inside."""
    r = BADGE_R
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=FILL)
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2), letter, fill=TEXT_COLOR, font=font)
