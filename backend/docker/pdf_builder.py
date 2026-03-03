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
MARGIN = 0.6 * inch

# Severity color map
SEV_COLORS = {
    "critical": ("#991b1b", "#fee2e2"),  # (text, background)
    "warning":  ("#92400e", "#fef3c7"),
    "info":     ("#1d4ed8", "#dbeafe"),
}
CATEGORY_ORDER = ["Links", "Accessibility", "Compliance", "Content", "Deliverability", "Technical"]


def build_pdf(desktop_img: bytes, mobile_img: bytes, links: list[dict],
              review: dict, subject: str = "", preheader: str = "") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)

    styles = getSampleStyleSheet()
    avail_w = W - 2 * MARGIN

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
    label = ParagraphStyle("label", parent=styles["Normal"], fontSize=8,
                            textColor=colors.HexColor("#9ca3af"))

    story = []

    # ── PAGE 1: Review Report ──────────────────────────────────────────────
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
        # Group by category, respecting the defined order
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
                    f'<font size="8" color="#6b7280">{issue.get("description", "")[:200]}</font>',
                    body
                )
                rec_cell = Paragraph(
                    f'<font size="8">{issue.get("recommendation", "")[:200]}</font>',
                    body
                )
                rows.append([sev_cell, title_cell, rec_cell])

            col_w = [0.8 * inch, (avail_w - 0.8 * inch) * 0.52, (avail_w - 0.8 * inch) * 0.48]
            tbl = Table(rows, colWidths=col_w, repeatRows=1)

            row_bgs = [colors.HexColor("#f9fafb")]
            for issue in cat_issues:
                sev = issue.get("severity", "info")
                _, bg_hex = SEV_COLORS.get(sev, ("#374151", "#f9fafb"))
                row_bgs.append(colors.HexColor(bg_hex))

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
            # Apply per-row severity background colors
            for row_idx, issue in enumerate(cat_issues, start=1):
                sev = issue.get("severity", "info")
                _, bg_hex = SEV_COLORS.get(sev, ("#374151", "#f9fafb"))
                tbl.setStyle(TableStyle([
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), colors.HexColor(bg_hex)),
                ]))

            story.append(tbl)
            story.append(Spacer(1, 0.1 * inch))
    else:
        story.append(Paragraph("No issues identified. The email passed all automated checks.", body))

    story.append(PageBreak())

    # ── PAGE 2: Annotated Desktop Screenshot ──────────────────────────────
    story.append(Paragraph("Email Campaign — Annotated PDF", h1))
    if subject:
        story.append(Paragraph(f"<b>Subject:</b> {subject}", meta))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("Desktop View (1200 px — Outlook / Microsoft 365)", label))
    story.append(Spacer(1, 0.08 * inch))
    story.append(RLImage(io.BytesIO(desktop_img), width=avail_w, height=avail_w * 0.58))
    story.append(PageBreak())

    # ── PAGE 3: Annotated Mobile Screenshot ───────────────────────────────
    story.append(Paragraph("Mobile View (390 px — iPhone 14)", label))
    story.append(Spacer(1, 0.08 * inch))
    mob_w = avail_w * 0.38
    story.append(RLImage(io.BytesIO(mobile_img), width=mob_w, height=mob_w * 2.16))
    story.append(PageBreak())

    # ── PAGE 4: Link Reference Table ──────────────────────────────────────
    story.append(Paragraph("Link Reference Table", h1))
    story.append(Spacer(1, 0.15 * inch))

    if links:
        rows = [["Ref", "Label", "URL"]]
        for lnk in links:
            rows.append([
                Paragraph(f"<b>{lnk['letter']}</b>", body),
                Paragraph(lnk["label"], body),
                Paragraph(f'<font size="7">{lnk["url"]}</font>', body),
            ])

        col_w = [0.45 * inch, 1.7 * inch, avail_w - 2.15 * inch]
        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0),  9),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ("GRID",          (0, 0), (-1, -1), 0.4, colors.HexColor("#e5e7eb")),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph("No annotated links found in this email.", small))

    doc.build(story)
    return buf.getvalue()
