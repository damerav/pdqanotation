"""
pdf_builder.py

Builds a 2-page annotated PDF matching the InDesign manual process:
  Page 1: Desktop Version — header block + link index + annotated screenshot
  Page 2: Mobile Version  — header block + link index + annotated screenshot

Each page is sized to fit its content exactly (8.5in wide, height varies).
"""

import io
from PIL import Image as PILImage
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Image as RLImage, PageBreak,
)

# Badge visual constants (matching image_annotator.py)
BADGE_COLOR = "#DC2626"

# Page margins
MARGIN = 0.4 * inch
PAGE_W = 8.5 * inch


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
    avail_w = PAGE_W - 2 * MARGIN

    styles = getSampleStyleSheet()

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

    page_styles = {
        "version_label": version_label,
        "meta_style": meta_style,
        "link_text": link_text,
        "styles": styles,
    }

    # Build page 1 (desktop) and page 2 (mobile) as separate flowable lists
    desktop_elements = _build_page(
        "DESKTOP VERSION", desktop_img, links, subject, preheader,
        avail_w, **page_styles,
    )
    mobile_elements = _build_page(
        "MOBILE VERSION", mobile_img, links, subject, preheader,
        avail_w, **page_styles,
    )

    # Estimate page heights from screenshot aspect ratios + header overhead
    header_h = _estimate_header_height(links)
    desktop_page_h = header_h + _img_render_height(desktop_img, avail_w) + 2 * MARGIN
    mobile_page_h = header_h + _img_render_height(mobile_img, avail_w) + 2 * MARGIN

    # Use the taller of the two as the page height so both fit
    page_h = max(desktop_page_h, mobile_page_h)

    doc = SimpleDocTemplate(
        buf,
        pagesize=(PAGE_W, page_h),
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
    )

    story = desktop_elements + [PageBreak()] + mobile_elements
    doc.build(story)
    return buf.getvalue()


def _build_single_page(
    version_text: str,
    screenshot_img: bytes,
    links: list[dict],
    subject: str,
    preheader: str,
) -> bytes:
    """Build a single-page PDF for one viewport (desktop or mobile)."""
    avail_w = PAGE_W - 2 * MARGIN
    styles = getSampleStyleSheet()

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

    # Calculate screenshot render dimensions
    pil_img = PILImage.open(io.BytesIO(screenshot_img))
    img_w, img_h = pil_img.size
    aspect = img_h / img_w
    render_w = avail_w
    render_h = render_w * aspect

    # Estimate header + link index height (rough: 200pt header + 20pt per link)
    header_h = 200 + len(links) * 22
    total_h = header_h + render_h + 2 * MARGIN + 40  # extra padding

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=(PAGE_W, total_h),
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )

    story = []

    # Version label box
    story.append(Paragraph(version_text, version_label))
    story.append(Spacer(1, 6))

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
        story.append(Paragraph(f"<b>{line}</b>", meta_style))

    story.append(Spacer(1, 10))

    # Link index
    if links:
        for lnk in links:
            letter = lnk.get("letter", "?")
            url = lnk.get("url", lnk.get("href", ""))
            label = lnk.get("label", "")

            label_esc = _esc(label) if label else ""
            url_esc = _esc(url)

            if label and "unsubscribe" in label.lower():
                display = f'<b>{label_esc}</b>'
            elif label:
                display = (
                    f'<b>{label_esc}</b><br/>'
                    f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
                    f'<font size="6" color="#666666">{url_esc}</font>'
                )
            else:
                display = url_esc

            badge_html = (
                f'<font color="{BADGE_COLOR}"><b>\u25cf</b></font>'
                f'&nbsp;&nbsp;<b>{letter}</b>&nbsp;&nbsp;&nbsp;'
                f'{display}'
            )
            story.append(Paragraph(badge_html, link_text))
            story.append(Spacer(1, 3))

    story.append(Spacer(1, 12))

    # Annotated screenshot
    story.append(RLImage(io.BytesIO(screenshot_img), width=render_w, height=render_h))

    doc.build(story)
    return buf.getvalue()


def _merge_pdfs(*pdf_bytes_list: bytes) -> bytes:
    """Merge multiple single-page PDFs into one multi-page PDF."""
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        from PyPDF2 import PdfReader, PdfWriter

    writer = PdfWriter()
    for pdf_data in pdf_bytes_list:
        reader = PdfReader(io.BytesIO(pdf_data))
        for page in reader.pages:
            writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _esc(text: str) -> str:
    """Escape HTML special characters for ReportLab Paragraph."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _img_render_height(img_bytes: bytes, avail_w: float) -> float:
    """Calculate the rendered height of an image at the available width."""
    pil_img = PILImage.open(io.BytesIO(img_bytes))
    img_w, img_h = pil_img.size
    return avail_w * (img_h / img_w)


def _estimate_header_height(links: list[dict]) -> float:
    """Rough estimate of header block height (version label + meta + link index)."""
    # Version label ~30pt, meta ~60pt, each link ~20pt, spacers ~30pt
    base = 120
    link_lines = len(links) * 22
    return base + link_lines


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

    # Link index — red circle badge + label (line 1) + URL (line 2)
    if links:
        for lnk in links:
            letter = lnk.get("letter", "?")
            url = lnk.get("url", lnk.get("href", ""))
            label = lnk.get("label", "")

            label_esc = _esc(label) if label else ""
            url_esc = _esc(url)

            if label and "unsubscribe" in label.lower():
                display = f'<b>{label_esc}</b>'
            elif label:
                display = (
                    f'<b>{label_esc}</b><br/>'
                    f'&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'
                    f'<font size="6" color="#666666">{url_esc}</font>'
                )
            else:
                display = url_esc

            badge_html = (
                f'<font color="{BADGE_COLOR}"><b>●</b></font>'
                f'&nbsp;&nbsp;<b>{letter}</b>&nbsp;&nbsp;&nbsp;'
                f'{display}'
            )
            elements.append(Paragraph(badge_html, link_text))
            elements.append(Spacer(1, 3))

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
