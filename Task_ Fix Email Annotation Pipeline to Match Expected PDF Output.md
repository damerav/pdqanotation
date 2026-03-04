# Task: Fix Email Annotation Pipeline to Match Expected PDF Output

## Context

This project automates a manual email annotation process previously done in Adobe InDesign. The current automated output does not match the expected output. Your job is to read the codebase, understand the problem, implement the fix across multiple files, and validate the result.

**Do not guess. Read every file listed in the "Files to Read First" section before writing any code.**

---

## Files to Read First

Before making any changes, read these files in order:

1. `backend/docker/html_parser.py` — how links are extracted from HTML
2. `backend/docker/bedrock_classifier.py` — how links are currently classified
3. `backend/docker/screenshot_generator.py` — how screenshots are captured and what coordinates are returned
4. `backend/docker/image_annotator.py` — how callout badges are currently drawn
5. `backend/docker/pdf_builder.py` — how the PDF is currently assembled
6. `backend/docker/handler.py` — how all modules are wired together

---

## Problem Description

### What the manual InDesign process produces (verified from the actual expected PDF)

The expected output is a **2-page PDF** with this exact structure:

**Page 1 — Desktop Version**
**Page 2 — Mobile Version**

Each page contains two sections stacked vertically:

#### Section A: Header Block (at the top of the page, above the screenshot)

A plain white block containing:
- A red-bordered label box: **"DESKTOP VERSION"** or **"MOBILE VERSION"**
- Email metadata in bold:
  - `To: <address@email.com>`
  - `From: PDQ Communications <info@pdqcom.com>`
  - `Initial Subject Line: [subject text]`
  - `Preheader: [preheader text]`
  - `Echo1 Subject Line: [echo1 subject]`
  - `Echo1 Preheader: [echo1 preheader]`
  - `Echo2 Subject Line: [echo2 subject]`
  - `Echo2 Preheader: [echo2 preheader]`
- A **link index list**: each entry is a **red circle badge** (A, B, C...) followed by the **full raw URL** of that link. The last entry uses a text description instead of a URL (e.g., `K  Links to PDQ Unsubscribe`).

#### Section B: Annotated Email Screenshot

The full rendered email screenshot placed directly below the header. **Red circle badges (A, B, C...) are placed directly on top of the email screenshot at the exact pixel location of each link element.** The badges are not in a margin — they sit on the email content itself, at the center of the clickable element (button, text link, image link).

---

### What the current code produces (the problems)

| File | Current Behaviour | Required Behaviour |
|---|---|---|
| `pdf_builder.py` | Generates a multi-page PDF with a review report, separate screenshot pages, and a separate link table | Must generate exactly **2 pages** (desktop + mobile), each with a header block followed by the annotated screenshot |
| `pdf_builder.py` | Link reference table uses human-readable labels | The link index must show the **full raw URL** for each badge letter |
| `image_annotator.py` | Badges placed in the right margin of the image, outside the email | Badges must be placed **directly on the email screenshot** at the **exact pixel coordinates** of each link element |
| `screenshot_generator.py` | Returns only `(desktop_bytes, mobile_bytes)` | Must also return link bounding boxes so the annotator knows where to place each badge |
| `handler.py` | Does not pass bounding box data to the annotator | Must unpack 4 return values and pass bboxes to `annotate_screenshot()` |

---

## Visual Specification — Verified from Actual Expected PDF

### Badge style
- Shape: **Perfect circle** (not oval, not rectangle)
- Fill color: **RGB(220, 38, 38)** — red
- Letter: **White, bold**, centered inside the circle
- Diameter: approximately **44px** at 1x scale (scale proportionally for retina screenshots)

### Badge placement
The badges are placed **directly on the email screenshot** at the location of each link:
- For **image links and CTA buttons**: badge is centered on the button/image
- For **text links**: badge is placed at the start or center of the linked text
- For **footer links**: badge is placed at the center of the footer link element
- The badge **overlaps the email content** — this is correct and expected

### Link index (header section)
The link index above the screenshot lists:
- **Red circle badge** (same style as on the screenshot) followed by the **full raw URL**
- For unsubscribe links that use a redirect or template variable: use the text description `"Links to PDQ Unsubscribe"` instead of the URL
- Links are listed in the order they appear in the HTML source

---

## Solution Instructions

### Step 1 — Update the EC2 Screenshot Service (`backend/screenshot_service/app.py`)

After rendering the HTML with Playwright, collect bounding boxes for every `<a href>` element:

```python
links_data = []
anchors = await page.query_selector_all("a[href]")
for i, anchor in enumerate(anchors):
    bbox = await anchor.bounding_box()
    href = await anchor.get_attribute("href") or ""
    text = (await anchor.inner_text()).strip()
    if bbox:
        center_x = (bbox["x"] + bbox["width"] / 2) * device_scale_factor
        center_y = (bbox["y"] + bbox["height"] / 2) * device_scale_factor
        links_data.append({
            "index": i,
            "href": href,
            "text": text,
            "center_x": center_x,
            "center_y": center_y,
        })
```

Return `desktop_links` and `mobile_links` in the response JSON alongside the base64 screenshots.

### Step 2 — Update `screenshot_generator.py`

Change the return signature of `capture_screenshots()`:

```python
def capture_screenshots(...) -> tuple[bytes, bytes, list[dict], list[dict]]:
    # returns: desktop_png, mobile_png, desktop_bboxes, mobile_bboxes
```

Parse `desktop_links` and `mobile_links` from the service response. Default to `[]` if not present.

### Step 3 — Rewrite `image_annotator.py`

The `annotate_screenshot()` function signature must become:

```python
def annotate_screenshot(
    screenshot_png: bytes,
    links: list[dict],
    viewport: str = "desktop",
    bboxes: list[dict] | None = None,
) -> bytes:
```

**Badge placement logic — badges go ON the email, not in the margin:**

1. Do **not** extend the canvas. Draw directly on the screenshot.
2. For each included link (where `include=True`), determine the badge center:
   - Match the link's URL to a bbox entry's `href` and use its `center_x`, `center_y`
   - If no bbox match is found, fall back to placing the badge at `(screenshot_width - 30, evenly_spaced_y)`
3. Draw a **filled red circle** at the matched coordinates:
   - Use `ImageDraw.ellipse([cx-22, cy-22, cx+22, cy+22])` for a 44px diameter circle
   - Fill: RGB(220, 38, 38)
4. Draw the white bold letter (A, B, C...) centered inside the circle

**Visual constants:**
- Badge diameter: 44px
- Badge fill: RGB(220, 38, 38)
- Letter color: white, bold
- No pointer lines, no margin extension

### Step 4 — Update `bedrock_classifier.py`

The classifier is used only to determine which links to **include or exclude** (filter out font CDNs, tracking pixels, empty hrefs, template variables). The **label** field is no longer used in the PDF — the raw URL is shown instead.

Update the prompt to:
- Use model `anthropic.claude-3-haiku-20240307-v1:0`
- Return `include: true/false` for each link
- Set `include: false` for: font CDN links, tracking pixels, empty hrefs, `javascript:` links, `mailto:` links that are not the primary unsubscribe
- For the unsubscribe link, set `include: true` and `label: "Links to PDQ Unsubscribe"`
- For all other links, the `label` field can be the anchor text (it is only used as a fallback display)

### Step 5 — Update `handler.py`

Update steps 4 and 5 in `_handle_process`:

```python
# Step 4 — Screenshots + bounding boxes
desktop_bytes, mobile_bytes, desktop_bboxes, mobile_bboxes = capture_screenshots(
    html_content, work_dir=work_dir, images_b64=images_b64,
)

# Step 5 — Annotate badges directly on the email screenshots
ann_desktop = annotate_screenshot(desktop_bytes, classified, "desktop", bboxes=desktop_bboxes)
ann_mobile = annotate_screenshot(mobile_bytes, classified, "mobile", bboxes=mobile_bboxes)
```

Also pass the email metadata (subject lines, preheader, from/to) to `build_pdf()`.

### Step 6 — Rewrite `pdf_builder.py`

The PDF must have exactly **2 pages**. Remove the review report pages and the standalone link reference table page entirely.

**Each page structure:**

```
┌─────────────────────────────────────────────────────────┐
│  [RED BORDER BOX] DESKTOP VERSION                       │
│                                                         │
│  To: <address@email.com>                                │
│  From: PDQ Communications <info@pdqcom.com>             │
│  Initial Subject Line: [subject]                        │
│  Preheader: [preheader]                                 │
│  Echo1 Subject Line: [echo1_subject]                    │
│  Echo1 Preheader: [echo1_preheader]                     │
│  Echo2 Subject Line: [echo2_subject]                    │
│  Echo2 Preheader: [echo2_preheader]                     │
│                                                         │
│  ● A  https://ad.doubleclick.net/ddm/clk/...            │
│  ● B  https://ad.doubleclick.net/ddm/clk/...            │
│  ● C  https://ad.doubleclick.net/ddm/clk/...            │
│  ...                                                    │
│  ● K  Links to PDQ Unsubscribe                          │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  [Full email screenshot with badges on it]       │   │
│  │  ● A (on hero image)                             │   │
│  │  ● B (on CTA button)                             │   │
│  │  ...                                             │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Implementation notes:**
- Use `reportlab` with a custom page size matching the screenshot width (do not force letter size — let the page height match the content)
- The header block is drawn with `reportlab` drawing primitives (Paragraph, Table, etc.)
- The annotated screenshot image is placed below the header using `reportlab.platypus.Image`
- For the link index list, draw each entry as: red circle with letter + URL text on the same line
- Use the raw URL from `classified[i]['href']` for the link index, except for unsubscribe links where `classified[i]['label'] == "Links to PDQ Unsubscribe"` — use the label text instead

---

## Validation Steps

After making all changes, run syntax checks:

```bash
python3 -m py_compile backend/docker/bedrock_classifier.py && echo "OK: bedrock_classifier"
python3 -m py_compile backend/docker/screenshot_generator.py && echo "OK: screenshot_generator"
python3 -m py_compile backend/docker/image_annotator.py && echo "OK: image_annotator"
python3 -m py_compile backend/docker/handler.py && echo "OK: handler"
python3 -m py_compile backend/docker/pdf_builder.py && echo "OK: pdf_builder"
python3 -m py_compile backend/screenshot_service/app.py && echo "OK: screenshot_service"
```

Then run the visual validation test:

```bash
cd backend/docker && python3 - << 'EOF'
from image_annotator import annotate_screenshot
from PIL import Image
import io

# Create a dummy white screenshot (simulating a 1200px wide email render)
img = Image.new("RGB", (2400, 4000), (255, 255, 255))
buf = io.BytesIO()
img.save(buf, format="PNG")
dummy_png = buf.getvalue()

# Simulate 3 classified links with bboxes
classified = [
    {"href": "https://example.com/cta1", "label": "CTA 1", "include": True},
    {"href": "https://example.com/pi", "label": "PI", "include": True},
    {"href": "https://example.com/unsub", "label": "Links to PDQ Unsubscribe", "include": True},
]
fake_bboxes = [
    {"href": "https://example.com/cta1", "center_x": 600.0, "center_y": 400.0},
    {"href": "https://example.com/pi", "center_x": 400.0, "center_y": 1600.0},
    {"href": "https://example.com/unsub", "center_x": 300.0, "center_y": 3800.0},
]

annotated = annotate_screenshot(dummy_png, classified, "desktop", bboxes=fake_bboxes)
result_img = Image.open(io.BytesIO(annotated))

# Canvas must NOT be wider than original (no margin extension)
assert result_img.width == 2400, f"FAIL: canvas was extended. Width={result_img.width}, expected 2400"
print(f"Canvas width unchanged: {result_img.width}px ✓")

# Red pixels must exist at the badge locations (center of each link)
pixels = result_img.load()
badge_positions = [(600, 400), (400, 1600), (300, 3800)]
for bx, by in badge_positions:
    r, g, b = pixels[bx, by]
    assert r > 180 and g < 80 and b < 80, f"FAIL: no red badge at ({bx},{by}), got RGB({r},{g},{b})"
    print(f"Red badge confirmed at ({bx},{by}): RGB({r},{g},{b}) ✓")

print("\nAll validation checks passed.")
EOF
```

**Expected output:**
```
Canvas width unchanged: 2400px ✓
Red badge confirmed at (600,400): RGB(220,38,38) ✓
Red badge confirmed at (400,1600): RGB(220,38,38) ✓
Red badge confirmed at (300,3800): RGB(220,38,38) ✓

All validation checks passed.
```

---

## Expected PDF Output — Definitive Specification

### Structure
- **Exactly 2 pages** — no more, no less
- Page 1: Desktop Version
- Page 2: Mobile Version

### Each page contains (top to bottom)

| Element | Details |
|---|---|
| Version label | Red-bordered box with text "DESKTOP VERSION" or "MOBILE VERSION" in red |
| Email metadata | To, From, Initial Subject Line, Preheader, Echo1 Subject, Echo1 Preheader, Echo2 Subject, Echo2 Preheader — all bold |
| Link index | Red circle badges A, B, C... each followed by the full raw URL on the same line; unsubscribe entry uses text "Links to PDQ Unsubscribe" |
| Annotated screenshot | Full email screenshot with red circle badges placed directly on the email at each link's location |

### Correct link index format (from actual expected PDF)

```
● A  https://ad.doubleclick.net/ddm/clk/621568076;428493034;n;gdpr=${GDPR};gdpr_consent=${GDPR_CONSENT_755}
● B  https://ad.doubleclick.net/ddm/clk/621883231;429065142;c;gdpr=${GDPR};gdpr_consent=${GDPR_CONSENT_755}
● C  https://ad.doubleclick.net/ddm/clk/621883234;429065145;i;gdpr=${GDPR};gdpr_consent=${GDPR_CONSENT_755}
● D  https://ad.doubleclick.net/ddm/clk/621883240;429065151;c;gdpr=${GDPR};gdpr_consent=${GDPR_CONSENT_755}
● E  https://ad.doubleclick.net/ddm/clk/621883243;429065154;i;gdpr=${GDPR};gdpr_consent=${GDPR_CONSENT_755}
● F  https://ad.doubleclick.net/ddm/clk/621883246;429065157;o;gdpr=${GDPR};gdpr_consent=${GDPR_CONSENT_755}
● G  https://ad.doubleclick.net/ddm/clk/621883249;429065160;l;gdpr=${GDPR};gdpr_consent=${GDPR_CONSENT_755}
● H  https://ad.doubleclick.net/ddm/clk/621883252;429065163;i;gdpr=${GDPR};gdpr_consent=${GDPR_CONSENT_755}
● I  https://ad.doubleclick.net/ddm/clk/621883255;429065166;o;gdpr=${GDPR};gdpr_consent=${GDPR_CONSENT_755}
● J  https://insmed.com/state-disclosure-information/
● K  Links to PDQ Unsubscribe
```

### What NOT to produce

- No separate Bedrock review report pages
- No standalone link reference table page
- No badges in the right margin outside the email
- No human-readable narration labels in the link index (show raw URLs)
- No pointer lines or connectors

---

## Definition of Done

- [ ] `screenshot_generator.py` returns 4 values: `desktop_png, mobile_png, desktop_bboxes, mobile_bboxes`
- [ ] `image_annotator.py` draws red **circles** directly **on the email screenshot** at each link's `center_x`, `center_y` coordinates — canvas width is **unchanged**
- [ ] `pdf_builder.py` produces exactly **2 pages** (desktop + mobile), each with header block (metadata + link index with raw URLs) followed by the annotated screenshot
- [ ] `handler.py` unpacks 4 return values from `capture_screenshots()` and passes bboxes to `annotate_screenshot()`
- [ ] All Python files pass `python3 -m py_compile <file>` with no errors
- [ ] Visual validation test passes with `All validation checks passed.`
- [ ] `git add` all changed files, `git commit -m "fix: annotation pipeline to match expected PDF output"`, `git push origin main`
