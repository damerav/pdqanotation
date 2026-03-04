"""
pdf_builder.py

Builds a 2-page annotated PDF matching the InDesign manual process:
  Page 1: Desktop Version — header block + link index + annotated screenshot
  Page 2: Mobile Version  — header block + link index + annotated screenshot
"""

import io
from PIL import Image as PILImage
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Image as RLImage, Table, TableStyle, PageBreak,
)
from reportlab.lib.enums import TA_LEFT

# Badge visual constants (matching image_annotator.py)
BADGE_COLOR = "#DC2626"
BADGE_TEXT = "#FFFFFF"

# Page margins
MARGIN = 0.4 * inch


def build_pdf(
    desktop_img: bytes,
    mobile_img: bytes,
    links: list[dict],
    review: dict,
    subject: str = "",
    preheader: str = "",
) -> bytes:
    """Build a 2-page annotated PDF with header blocks and screenshots."""
    buf = io.BytesIO()

    # Use A4-ish width but let height be flexible
    PAGE_W = 8.5 * inch
    PAGE_H = 50 * inch  # tall enough for any content; SimpleDocTemplate handles it
    doc = SimpleDocTemplate(
        buf,
        pagesize=(PAGE_W, PAGE_H),
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    avail_w = PAGE_W - 2 * MARGIN
    styles = getSampleStyleSheet()

    # Style definitions
    version_label = ParagraphStyle(
        "version_label", parent=styles["Normal"], fontSize=14,
        textColor=colors.HexColor("#DC2626"), fontName="Helvetica-Bold",
        borderColor=colors.HexColor("#DC2626"), borderWidth=1,
        borderPadding=6, spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        "meta", parent=styles["Normal"], fontSize=10,
        fontName="Helvetica-Bold", leading=14, spaceAfter=2,
    )
    link_text = ParagraphStyle(
        "link_text", parent=styles["Normal"], fontSize=8,
        leading=11, textColor=colors.HexColor("#333333"),
    )

    story = []

    # ── PAGE 1: Desktop Version ───────────────────────────────────────
    story.extend(_build_page(
        "DESKTOP VERSION", desktop_img, links, subject, preheader,
        avail_w, version_label, meta_style, link_text, styles,
    ))

    story.append(PageBreak())

    # ── PAGE 2: Mobile Version ────────────────────────────────────────
    story.extend(_build_page(
        "MOBILE VERSION", mobile_img, links, subject, preheader,
        avail_w, version_label, meta_style, link_text, styles,
    ))

    doc.build(story)
    return buf.getvalue()


def _build_page(
    version_text: str,
    screenshot_img: bytes,
    links: list[dict],
    subject: str,
    preheader: str,
    avail_w: float,
    version_label: ParagraphStyle,
    meta_style: ParagraphStyle,
    link_text: ParagraphStyle,
    styles,
) -> list:
    """Build the flowable elements for one page (desktop or mobile)."""
    elements = []

    # Version label box
    elements.append(Paragraph(version_text, version_label))
    elements.append(Spacer(1, 6))

    # Email metadata
    meta_lines = [
        'To: &lt;address@email.com&gt;',
        'From: PDQ Communications &lt;info@pdqcom.com&gt;',
    ]
    if subject:
        meta_lines.append(f'Initial Subject Line: {_esc(subject)}')
    if preheader:
        meta_lines.append(f'Preheader: {_esc(preheader)}')

    for line in meta_lines:
        elements.append(Paragraph(f"<b>{line}</b>", meta_style))

    elements.append(Spacer(1, 10))

    # Link index — red circle badge + raw URL on each line
    if links:
        for lnk in links:
            letter = lnk.get("letter", "?")
            url = lnk.get("url", lnk.get("href", ""))
            label = lnk.get("label", "")

            # Use label text for unsubscribe, raw URL for everything else
            if "unsubscribe" in label.lower():
                display = _esc(label)
            else:
                display = _esc(url)

            badge_html = (
                f'<font color="{BADGE_COLOR}"><b>●</b></font>'
                f'&nbsp;&nbsp;<b>{letter}</b>&nbsp;&nbsp;&nbsp;'
                f'<font size="7">{display}</font>'
            )
            elements.append(Paragraph(badge_html, link_text))

    elements.append(Spacer(1, 12))

    # Annotated screenshot — full width
    pil_img = PILImage.open(io.BytesIO(screenshot_img))
    img_w, img_h = pil_img.size
    aspect = img_h / img_w
    render_w = avail_w
    render_h = render_w * aspect

    elements.append(RLImage(io.BytesIO(screenshot_img), width=render_w, height=render_h))

    return elements


def _esc(text: str) -> str:
    """Escape HTML special characters for ReportLab Paragraph."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
