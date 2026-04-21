# Bugfix Requirements Document

## Introduction

The Email Campaign Annotator pipeline is systematically missing links during annotation, producing 75–95% accuracy across client-tested campaigns instead of the expected ~100%. Three distinct root causes have been identified through analysis of 7 campaigns tested by the client:

1. The AI classifier (`bedrock_classifier.py`) incorrectly marks valid user-facing links as `include: false`, removing them from the output entirely — particularly image-only links, CTA buttons with generic text like "Click here", and ghost-link elements.
2. The HTML parser (`html_parser.py`) deduplicates links using a `(url, anchor_text.lower())` key, which causes image-wrapped links with empty anchor text sharing the same URL to collide — only the first survives.
3. Letter assignment (`bedrock_classifier.py`) follows HTML source order rather than visual rendering order, causing letter mismatches in table-based email layouts where HTML order differs from top-to-bottom visual order.

These bugs directly impact the tool's core value proposition: producing accurate annotated PDF proofs for pharmaceutical email campaigns where every link must be accounted for.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN an `<a href>` tag contains generic anchor text such as "Click here" THEN the system classifies it as `include: false` and omits it from the annotated output, even though it is a valid user-facing CTA link (e.g., Campaign 26-030: "Click here" button linking to Companion Program was missed)

1.2 WHEN an `<a href>` tag wraps an image with no text content (empty anchor text) THEN the system classifies it as `include: false` because the anchor text appears non-descriptive, removing a valid visual link from the output (e.g., Campaign 26-026: image-wrapped links at HTML lines 106 and 136 were missed)

1.3 WHEN an `<a href>` tag uses a CSS class like `ghost-link` that visually overlays content THEN the system classifies it as `include: false` because the link appears to be a tracking or utility element rather than user-facing content (e.g., Campaign 26-010: "Tecentric Logo" ghost-link at HTML line 169 was missed)

1.4 WHEN two or more `<a href>` tags share the same URL but have empty anchor text (e.g., two different image-wrapped links pointing to the same tracking URL) THEN the system's deduplication logic using the key `(url, anchor_text.lower())` treats them as duplicates and only keeps the first occurrence, silently dropping subsequent links that are visually distinct elements in the email

1.5 WHEN an HTML email uses table-based layout where the HTML source order of links differs from the visual top-to-bottom rendering order THEN the system assigns letter labels (A, B, C, ...) based on HTML parse order rather than visual order, causing letter mismatches between the annotated PDF and the actual visual layout (e.g., Campaign 25-256: "Pricing Disclosure Information" labeled E instead of C)

1.6 WHEN the system reports "Annotation Confidence: 100%" but has actually missed one or more links THEN the confidence metric is misleading because it measures badge placement accuracy against classified links rather than against total links present in the HTML (e.g., Campaign 26-030: 100% confidence reported but only 3 of 4 links detected)

### Expected Behavior (Correct)

2.1 WHEN an `<a href>` tag contains generic anchor text such as "Click here" THEN the system SHALL include it in the annotated output as a valid user-facing link, since any `<a href>` with a non-tracking, non-stylesheet URL that a user can click is a content link

2.2 WHEN an `<a href>` tag wraps an image with no text content (empty anchor text) THEN the system SHALL include it in the annotated output, recognizing that image-wrapped links are standard email design patterns representing clickable visual elements

2.3 WHEN an `<a href>` tag uses a CSS class like `ghost-link` that visually overlays content THEN the system SHALL include it in the annotated output, since ghost-links are intentional design elements that create clickable regions over visual content

2.4 WHEN two or more `<a href>` tags share the same URL but have empty anchor text THEN the system SHALL treat them as distinct links by incorporating positional information (e.g., HTML source line number or element index) into the deduplication key, preserving all visually distinct link elements

2.5 WHEN an HTML email uses table-based layout THEN the system SHALL assign letter labels based on the visual top-to-bottom rendering order of links as they appear on the rendered page, not based on HTML source order

2.6 WHEN the system calculates annotation confidence THEN the system SHALL compute it as the ratio of detected-and-placed links to total `<a href>` links present in the HTML (after filtering only font stylesheets, tracking pixels, and mailto/tel/javascript protocols), so that missed links are reflected in a lower confidence score

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a link URL points to a font stylesheet (fonts.googleapis.com, fonts.gstatic.com) or uses mailto:, tel:, or javascript: protocols THEN the system SHALL CONTINUE TO exclude these from the annotated output

3.2 WHEN two `<a href>` tags have the same URL and the same non-empty anchor text THEN the system SHALL CONTINUE TO deduplicate them, keeping only one instance since they represent the same visual element repeated

3.3 WHEN the AI classifier is unavailable or returns an error THEN the system SHALL CONTINUE TO fall back to including all links with generic labels ("Link 1", "Link 2", etc.) so the pipeline produces a PDF without AI-generated labels

3.4 WHEN a link has descriptive anchor text and a unique URL THEN the system SHALL CONTINUE TO classify and label it correctly with a human-readable label

3.5 WHEN the email layout is single-column with links in natural HTML source order matching visual order THEN the system SHALL CONTINUE TO assign letters sequentially (A, B, C, ...) in the same order as before
