import io
from PIL import Image, ImageDraw, ImageFont

CIRCLE_R = 16
FILL = (220, 50, 50)
TEXT_COLOR = (255, 255, 255)
FONT_SIZE = 18


def annotate_screenshot(img_bytes: bytes, links: list[dict], viewport: str) -> bytes:
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img)
    width, height = img.size

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", FONT_SIZE)
    except (IOError, OSError):
        font = ImageFont.load_default()

    n = len(links)
    if n == 0:
        return img_bytes

    # Place callouts in a right-side column, evenly spaced vertically.
    # For production, replace with Playwright element.bounding_box() coordinates.
    x = width - 28
    for i, link in enumerate(links):
        y = int((i + 1) * height / (n + 1))
        _draw_callout(draw, x, y, link["letter"], font)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _draw_callout(draw, cx, cy, letter, font):
    r = CIRCLE_R
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=FILL)
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2, cy - th // 2), letter, fill=TEXT_COLOR, font=font)
