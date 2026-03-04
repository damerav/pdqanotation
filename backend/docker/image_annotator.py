import io
from PIL import Image, ImageDraw, ImageFont

BOX_W = 28
BOX_H = 24
FILL = (220, 50, 50)
TEXT_COLOR = (255, 255, 255)
FONT_SIZE = 16
MARGIN_RIGHT = 8  # gap from right edge


def annotate_screenshot(img_bytes: bytes, links: list[dict], viewport: str) -> bytes:
    """Overlay lettered rectangular callout markers on the right margin of the screenshot."""
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

    # Place callouts evenly spaced along the right margin
    x = width - BOX_W - MARGIN_RIGHT
    for i, link in enumerate(links):
        y = int((i + 1) * height / (n + 1)) - BOX_H // 2
        _draw_callout(draw, x, y, link["letter"], font)

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _draw_callout(draw: ImageDraw.ImageDraw, x: int, y: int, letter: str, font) -> None:
    """Draw a red rectangular box with a white letter inside."""
    # Draw rounded-corner rectangle (using regular rectangle + slight rounding)
    r = 4  # corner radius
    x2, y2 = x + BOX_W, y + BOX_H
    draw.rounded_rectangle([x, y, x2, y2], radius=r, fill=FILL)

    # Center the letter in the box
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = x + (BOX_W - tw) // 2
    ty = y + (BOX_H - th) // 2
    draw.text((tx, ty), letter, fill=TEXT_COLOR, font=font)
