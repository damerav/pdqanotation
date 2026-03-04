import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer,
    Image as RLImage, Table, TableStyle, PageBreak, HRFlowable,
)

W, H = A4
MARGIN = 0.5 * inch

# Severity color map
SEV_COLORS = {
    "critical": ("#991b1b", "#fee2e2"),
    "warning":  ("#92400e", "#fef3c7"),
    "info":     ("#1d4ed8", "#dbeafe"),
}
CATEGORY_ORDER = [
    "Links", "Accessibility", "Compliance", "Content", "Deliverability", "Technical",
]


def build_pdf(desktop_img: bytes, mobile_img: bytes, links: list[dict],
              review: dict, subject: str = "", preheader: str = "") -> bytes:
    """Build the annotated PDF with review report, annotated screenshots, and link table."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)

    styles = getSampleStyleSheet()
    avail_w = W - 2 * MARGIN
    avail_h = H - 2 * MARGIN

    # Style definitions
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16,
                         textColor=colors.HexColor("#1a1a2e"), spaceAfter=4, spaceBefore=0)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12,
                         textColor=colors.HexColor("#1a1a2e"), spaceAfter=4, spaceBefore=10)
    meta = ParagraphStyle("meta", parent=styles["Normal"], fontSize=9,
                           textColor=colors.HexColor("#6b7280"), spaceAfter=2)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, leading=14)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8,
                            textColor=colors.HexColor("#9ca3af"))
    label_style = ParagraphStyle("label", parent=styles["Normal"], fontSize=8,
                            textColor=colors.HexColor("#9ca3af"))

    story = []

    # ── PAGE 1+: Review Report ─────────────────────────────────────────
    story.append(Paragraph("Email Campaign — Quality Review Report", h1))
    if subject:
        story.append(Paragraph(f"<b>Subject:</b> {subject}", meta))
    if preheader:
        story.append(Paragraph(f"<b>Preheader:</b> {preheader}", meta))
    story.append(Spacer(1, 0.15 * inch))

    # Score + summary banner
    score = review.get("overall_score")
    summary = review.get("overall_summary", "")
    counts = review.get("issue_counts", {})
    critical_n = counts.get("critical", 0)
    warning_n = counts.get("warning", 0)
    info_n = counts.get("info", 0)

    if score is not None:
        score_color = colors.HexColor("#166534") if score >= 80 else \
                      colors.HexColor("#92400e") if score >= 60 else \
                      colors.HexColor("#991b1b")
        score_data = [[
            Paragraph(f'<font size="28" color="{score_color.hexval()}">'
                      f'<b>{score}</b></font><font size="12" color="#6b7280">/100</font>', body),
            Paragraph(
                f'<b>Quality Score</b><br/>'
                f'<font size="8" color="#991b1b">● {critical_n} critical</font>  '
                f'<font size="8" color="#92400e">● {warning_n} warnings</font>  '
                f'<font size="8" color="#1d4ed8">● {info_n} info</font><br/><br/>'
                f'<font size="9" color="#374151">{summary}</font>', body),
        ]]
        score_tbl = Table(score_data, colWidths=[1.2 * inch, avail_w - 1.2 * inch])
        score_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")),
            ("BOX",        (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING",   (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
        ]))
        story.append(score_tbl)
        story.append(Spacer(1, 0.2 * inch))

    # Issues grouped by category
    issues = review.get("issues", [])
    if issues:
        grouped = {cat: [] for cat in CATEGORY_ORDER}
        grouped["Other"] = []
        for issue in issues:
            cat = issue.get("category", "Other")
            grouped.setdefault(cat, []).append(issue)

        for cat in list(CATEGORY_ORDER) + ["Other"]:
            cat_issues = grouped.get(cat, [])
            if not cat_issues:
                continue

            story.append(Paragraph(cat, h2))

            rows = [["Severity", "Issue", "Recommendation"]]
            for issue in cat_issues:
                sev = issue.get("severity", "info")
                txt_c, bg_c = SEV_COLORS.get(sev, ("#374151", "#f3f4f6"))

                sev_cell = Paragraph(
                    f'<font color="{txt_c}"><b>{sev.upper()}</b></font>',
                    ParagraphStyle("sev", parent=body, fontSize=8)
                )
                title_cell = Paragraph(
                    f'<b>{issue.get("title", "")}</b><br/>'
                    f'<font size="8" color="#6b7280">'
                    f'{issue.get("description", "")[:200]}</font>',
                    body
                )
                rec_cell = Paragraph(
                    f'<font size="8">{issue.get("recommendation", "")[:200]}</font>',
                    body
                )
                rows.append([sev_cell, title_cell, rec_cell])

            col_w = [
                0.8 * inch,
                (avail_w - 0.8 * inch) * 0.52,
                (avail_w - 0.8 * inch) * 0.48,
            ]
            tbl = Table(rows, colWidths=col_w, repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND",   (0, 0), (-1, 0),  colors.HexColor("#1a1a2e")),
                ("TEXTCOLOR",    (0, 0), (-1, 0),  colors.white),
                ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
                ("FONTSIZE",     (0, 0), (-1, 0),  8),
                ("GRID",         (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
                ("VALIGN",       (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING",  (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING",   (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
            ]))
            for row_idx, issue in enumerate(cat_issues, start=1):
                sev = issue.get("severity", "info")
                _, bg_hex = SEV_COLORS.get(sev, ("#374151", "#f9fafb"))
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, row_idx), (-1, row_idx),
                     colors.HexColor(bg_hex)),
                ]))

            story.append(tbl)
            story.append(Spacer(1, 0.1 * inch))
    else:
        story.append(Paragraph(
            "No issues identified. The email passed all automated checks.", body))

    story.append(PageBreak())

    # ── PAGE: Annotated Desktop Screenshot + Link Reference ───────────
    story.append(Paragraph("Email Campaign — Annotated PDF", h1))
    if subject:
        story.append(Paragraph(f"<b>Subject:</b> {subject}", meta))
    story.append(Spacer(1, 0.08 * inch))

    # Link reference table — compact, at the top of the annotated page
    if links:
        story.append(Paragraph("Link Reference", h2))
        ref_rows = [["Ref", "Label", "URL"]]
        for lnk in links:
            ref_rows.append([
                Paragraph(f"<b>{lnk['letter']}</b>", body),
                Paragraph(lnk["label"], small),
                Paragraph(
                    f'<font size="6">{lnk["url"]}</font>', small),
            ])

        ref_col_w = [0.35 * inch, 1.4 * inch, avail_w - 1.75 * inch]
        ref_tbl = Table(ref_rows, colWidths=ref_col_w, repeatRows=1)
        ref_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0), 7),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#f9fafb")]),
            ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        story.append(ref_tbl)
        story.append(Spacer(1, 0.1 * inch))

    # Desktop screenshot — fill remaining page width
    story.append(Paragraph(
        "Desktop View (1200 px — Outlook / Microsoft 365)", label_style))
    story.append(Spacer(1, 0.05 * inch))

    # Use the full available width; let ReportLab scale height proportionally
    from PIL import Image as PILImage
    desk_pil = PILImage.open(io.BytesIO(desktop_img))
    desk_w, desk_h = desk_pil.size
    desk_aspect = desk_h / desk_w
    img_w = avail_w
    img_h = img_w * desk_aspect
    # Cap height so it doesn't overflow the page
    max_img_h = avail_h * 0.65
    if img_h > max_img_h:
        img_h = max_img_h

    story.append(RLImage(io.BytesIO(desktop_img), width=img_w, height=img_h))
    story.append(PageBreak())

    # ── PAGE: Annotated Mobile Screenshot ─────────────────────────────
    story.append(Paragraph("Mobile View (390 px — iPhone 14)", label_style))
    story.append(Spacer(1, 0.08 * inch))

    mob_pil = PILImage.open(io.BytesIO(mobile_img))
    mob_w, mob_h = mob_pil.size
    mob_aspect = mob_h / mob_w
    # Mobile: use ~40% of page width, scale height proportionally
    mob_img_w = avail_w * 0.4
    mob_img_h = mob_img_w * mob_aspect
    max_mob_h = avail_h * 0.9
    if mob_img_h > max_mob_h:
        mob_img_h = max_mob_h
        mob_img_w = mob_img_h / mob_aspect

    story.append(RLImage(io.BytesIO(mobile_img), width=mob_img_w, height=mob_img_h))

    doc.build(story)
    return buf.getvalue()
