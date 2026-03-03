# Skill: Annotated PDF Generation

**Skill ID:** pdf-generation
**Applies to:** `pdf_builder.py`, `image_annotator.py`
**Last updated:** March 03, 2026

---

## Overview

This skill defines the patterns and standards for generating the annotated PDF proof document. The PDF is the primary deliverable of the entire pipeline and must be consistent, professional, and readable by non-technical email marketing professionals.

---

## PDF Structure

The PDF always contains exactly three pages in this order. Do not change the page order.

| Page | Content | Orientation | Purpose |
|---|---|---|---|
| 1 | Review Report | Portrait (A4) | AI quality assessment with score, summary, and all issues |
| 2 | Desktop View | Landscape (A4) | Annotated desktop screenshot with callout legend |
| 3 | Mobile View | Portrait (A4) | Annotated mobile screenshot with callout legend |

---

## Skill 1: Review Report Page (Page 1)

### Score Colour Coding

The quality score must always be displayed with consistent colour coding that matches the SES delivery email. Never change these thresholds or colours without updating both `pdf_builder.py` and `handler.py` (the `_send_email` function).

| Score Range | Colour (Hex) | Meaning |
|---|---|---|
| 80–100 | `#166534` (dark green) | Good — meets quality standards |
| 60–79 | `#92400e` (dark amber) | Fair — improvements recommended |
| 0–59 | `#991b1b` (dark red) | Poor — significant issues require attention |
| `None` | `#6b7280` (grey) | Review unavailable |

### Issue Row Colour Coding

Each issue row in the issues table uses a background colour to indicate severity:

| Severity | Background | Text |
|---|---|---|
| `critical` | `#fee2e2` (light red) | `#991b1b` (dark red) |
| `warning` | `#fef3c7` (light amber) | `#92400e` (dark amber) |
| `info` | `#dbeafe` (light blue) | `#1d4ed8` (dark blue) |

### Page 1 Layout Pattern

```python
# ReportLab pattern for Page 1
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Spacer

def build_review_page(canvas, review: dict, filename: str, job_id: str):
    # Header bar (dark navy background)
    canvas.setFillColorRGB(0.102, 0.102, 0.180)  # #1a1a2e
    canvas.rect(0, A4[1] - 60, A4[0], 60, fill=1, stroke=0)
    
    # Score circle
    score = review.get("overall_score")
    score_color = _score_color(score)
    canvas.setFillColor(score_color)
    canvas.circle(80, A4[1] - 120, 35, fill=1, stroke=0)
    canvas.setFillColorRGB(1, 1, 1)
    canvas.setFont("Helvetica-Bold", 24)
    canvas.drawCentredString(80, A4[1] - 128, str(score) if score else "N/A")
    
    # Issues table
    # ... (see pdf_builder.py for full implementation)
```

---

## Skill 2: Screenshot Annotation (image_annotator.py)

### Callout Badge Design

Each callout badge is a filled circle with a white letter. The design parameters are fixed and must not be changed without updating the legend renderer.

| Parameter | Value | Notes |
|---|---|---|
| Circle diameter | 28 px | Visible but not obstructive |
| Fill colour | `#e94560` (red) | Matches the app's brand colour |
| Text colour | White `#ffffff` | |
| Font | Helvetica Bold, 14pt | |
| Border | 2px white stroke | Improves visibility on dark backgrounds |

### Callout Positioning

Callouts are positioned at the link's approximate location in the rendered screenshot. Since Playwright does not return element bounding boxes directly, the current implementation uses a vertical distribution algorithm that spaces callouts evenly down the screenshot height, proportional to the link's position in the HTML source order.

For Sprint 1, when the Playwright MCP is integrated, replace this with exact bounding box positioning using the MCP's element coordinate API.

```python
# Current positioning (proportional, approximate)
def _estimate_y_position(link_index: int, total_links: int, image_height: int) -> int:
    """Estimate vertical position proportional to link order in HTML."""
    margin = image_height * 0.1
    usable_height = image_height - (2 * margin)
    return int(margin + (link_index / max(total_links - 1, 1)) * usable_height)

# Future positioning (exact, requires Playwright MCP bounding boxes)
def _exact_y_position(bounding_box: dict) -> int:
    return int(bounding_box["y"] + bounding_box["height"] / 2)
```

### Legend Format

The callout legend is rendered below each screenshot. Each row contains the letter badge, the label, and the truncated URL (maximum 80 characters). URLs longer than 80 characters are truncated with `...`.

---

## Skill 3: Handling Missing or Failed Components

The PDF builder must handle the case where any upstream component fails. These are the required fallback behaviours:

| Missing Component | Fallback Behaviour |
|---|---|
| `review` is `None` | Skip Page 1 entirely; start with Page 2 (desktop) |
| `review.overall_score` is `None` | Display "N/A" in grey instead of a score |
| `review.issues` is empty | Display "No issues detected" on Page 1 |
| Desktop screenshot fails | Display "Screenshot unavailable" placeholder on Page 2 |
| Mobile screenshot fails | Display "Screenshot unavailable" placeholder on Page 3 |
| No included links (all filtered) | Skip callout overlay; display plain screenshot |

The PDF must always be generated and delivered, even if all three components fail. A PDF with only a "processing error" message is more useful to the client than no PDF at all.

---

## Skill 4: Adding a New PDF Page

When adding a new page to the PDF (e.g., a brand compliance page in Sprint 1), follow this pattern:

1. Add the new page function to `pdf_builder.py` following the existing `_build_review_page()` pattern.
2. Call the new function in the correct position in `build_pdf()`.
3. Update the page count in the PDF header.
4. Update `requirements.md` (REQ-PDF-01) to include the new page.
5. Update `design.md` (Section 2.9) to document the new page.
6. Add a test case in `tests/unit/test_pdf_builder.py` that verifies the new page is present in the output.
