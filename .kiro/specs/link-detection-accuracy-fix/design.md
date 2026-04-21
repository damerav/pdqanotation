# Link Detection Accuracy Fix — Bugfix Design

## Overview

The Email Campaign Annotator pipeline is missing links and misordering letter labels across four modules. The root causes span the full pipeline: the HTML parser silently drops image-wrapped links sharing a URL via deduplication collision on empty anchor text; the AI classifier incorrectly excludes valid links with generic text, image-only content, or ghost-link patterns; letter assignment follows HTML source order instead of visual rendering order from Playwright bounding boxes; and the confidence metric measures badge placement against classified links rather than total extractable links, masking missed detections.

The fix strategy is surgical: patch each module at its specific failure point while preserving all existing behavior for non-buggy inputs (mouse-click-style links with descriptive text, single-column layouts, font/mailto/tel filtering).

## Glossary

- **Bug_Condition (C)**: The set of inputs where the pipeline produces incorrect output — links with empty/generic anchor text, duplicate URLs with empty text, table-based layouts with non-sequential visual order, or confidence calculated against classified-only links
- **Property (P)**: The desired behavior — all user-facing `<a href>` links are detected, deduplicated correctly, labeled in visual top-to-bottom order, and confidence reflects total extractable links
- **Preservation**: Existing behaviors that must remain unchanged — font/mailto/tel filtering, same-URL-same-text deduplication, fallback classification, descriptive-text labeling, single-column sequential ordering
- **`extract_links()`**: Function in `html_parser.py` that parses `<a href>` tags from HTML and returns deduplicated link dicts
- **`classify_links()`**: Function in `bedrock_classifier.py` that sends links to Bedrock for labeling and filtering, then assigns letter labels
- **`annotate_screenshot()`**: Function in `image_annotator.py` that places red circle badges on screenshots at link positions
- **`_collect_link_bboxes()`**: Function in `screenshot_service.py` that extracts bounding box coordinates for all `<a href>` elements via Playwright
- **bboxes**: Bounding box data from Playwright containing `center_x`, `center_y`, `right_x` for each rendered link element

## Bug Details

### Bug Condition

The bug manifests across four distinct failure modes in the annotation pipeline. Links are silently dropped, misordered, or miscounted whenever the input HTML contains image-wrapped links, generic CTA text, ghost-link overlays, duplicate URLs with empty anchor text, or table-based multi-column layouts.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type HTMLEmailContent
  OUTPUT: boolean

  links := extractAllAnchorTags(input.html)

  -- Bug 1: Classifier drops valid links
  hasGenericTextLinks := ANY link IN links WHERE
    link.anchorText IN ["Click here", "Learn more", "Read more", "Shop now", ""]
    AND link.url IS NOT fontStylesheet AND NOT mailto AND NOT tel AND NOT javascript
  
  -- Bug 2: Dedup collision on empty anchor text
  hasEmptyTextDuplicateURLs := ANY (link_a, link_b) IN links WHERE
    link_a.url == link_b.url
    AND link_a.anchorText == ""
    AND link_b.anchorText == ""
    AND link_a.elementIndex != link_b.elementIndex
  
  -- Bug 3: Visual order != HTML source order
  hasNonSequentialVisualOrder := ANY (link_i, link_j) IN links WHERE
    link_i.htmlSourceIndex < link_j.htmlSourceIndex
    AND link_i.visualY > link_j.visualY
  
  -- Bug 4: Confidence denominator is wrong
  totalExtractable := COUNT(links WHERE NOT fontStylesheet AND NOT mailto/tel/javascript)
  classifiedIncluded := COUNT(links WHERE classifier.include == true)
  hasConfidenceGap := classifiedIncluded < totalExtractable

  RETURN hasGenericTextLinks
         OR hasEmptyTextDuplicateURLs
         OR hasNonSequentialVisualOrder
         OR hasConfidenceGap
END FUNCTION
```

### Examples

- **Campaign 26-030**: "Click here" CTA button linking to Companion Program — classifier marks `include: false` due to generic anchor text. Expected: included as a valid link with label like "Companion Program CTA"
- **Campaign 26-026**: Two `<a href>` tags at HTML lines 106 and 136 wrapping different images but sharing the same tracking URL with empty anchor text — dedup key `(url, "")` collides, second link silently dropped. Expected: both links preserved as distinct visual elements
- **Campaign 26-010**: Ghost-link `<a href class="ghost-link">` overlaying "Tecentric Logo" at HTML line 169 — classifier marks `include: false` as it appears to be a utility element. Expected: included as a valid clickable region
- **Campaign 25-256**: Table-based layout where "Pricing Disclosure Information" appears visually as the 3rd link (C) but is labeled E because it's the 5th `<a>` tag in HTML source order. Expected: letter C based on visual Y-position
- **Campaign 26-030**: System reports "Annotation Confidence: 100%" but only detected 3 of 4 links — confidence denominator uses classified link count (3) instead of total extractable count (4). Expected: confidence = 75%

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Links to font stylesheets (`fonts.googleapis.com`, `fonts.gstatic.com`) must continue to be excluded
- Links using `mailto:`, `tel:`, or `javascript:` protocols must continue to be excluded
- Links with fragment-only hrefs (`#`) must continue to be excluded
- Two `<a href>` tags with the same URL AND the same non-empty anchor text must continue to be deduplicated to one instance
- When the Bedrock classifier is unavailable, the fallback must continue to include all links with generic labels ("Link 1", "Link 2", etc.)
- Links with descriptive anchor text and unique URLs must continue to receive accurate human-readable labels from the classifier
- In single-column emails where HTML source order matches visual order, letter assignment must remain sequential (A, B, C, ...)
- Mouse-click badge placement behavior in `image_annotator.py` must remain unchanged for links that already have correct bounding boxes
- PDF layout, email delivery, and S3 storage behavior must remain completely unchanged

**Scope:**
All inputs that do NOT involve the four bug conditions should be completely unaffected by this fix. This includes:
- Emails with only descriptive, unique-text links
- Single-column layouts with natural HTML ordering
- Emails where all links have non-empty, distinct anchor text
- The existing font/protocol filtering logic

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Classifier Over-Filtering (bedrock_classifier.py)**: The AI system prompt instructs the model to set `include: false` for links it deems non-user-facing. The prompt lacks explicit guidance that image-only links (empty anchor text), generic CTA text ("Click here"), and ghost-link overlays are all valid user-facing links. The model interprets empty/generic anchor text as a signal of a tracking pixel or duplicate, when in email design these are standard patterns.

2. **Deduplication Key Collision (html_parser.py)**: The `seen` set uses `(url, anchor.lower())` as the dedup key. When two visually distinct `<a>` tags share the same URL and both have empty anchor text (common for image-wrapped links), the key `(url, "")` is identical for both, causing the second to be silently dropped. The fix requires incorporating positional information (e.g., element index or source line) into the dedup key for empty-text links.

3. **Source-Order Letter Assignment (bedrock_classifier.py)**: The `classify_links()` function assigns letters A, B, C... by iterating `raw_links` in HTML parse order. For table-based email layouts, HTML source order can differ significantly from visual top-to-bottom rendering order. The fix requires reordering classified links by their visual Y-position (from Playwright bounding boxes) before assigning letters.

4. **Wrong Confidence Denominator (image_annotator.py)**: The confidence metric is `matched_count / total_count * 100` where `total_count` is the number of classified links with letters. This means links dropped by the classifier are never counted in the denominator, so confidence can be 100% even when links are missing. The fix requires passing the total extractable link count (from `html_parser.py`) into the confidence calculation.

## Correctness Properties

Property 1: Bug Condition — All User-Facing Links Detected

_For any_ HTML email input containing `<a href>` tags with generic anchor text ("Click here", etc.), empty anchor text (image-wrapped links), or ghost-link CSS classes, the fixed pipeline SHALL include all such links in the annotated output, provided their URLs are not font stylesheets, tracking pixels, or mailto/tel/javascript protocols.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Bug Condition — Empty-Text Links Deduplicated Correctly

_For any_ HTML email input containing two or more `<a href>` tags sharing the same URL but with empty anchor text, the fixed `extract_links()` function SHALL treat them as distinct links by incorporating positional information into the deduplication key, preserving all visually distinct link elements.

**Validates: Requirements 2.4**

Property 3: Bug Condition — Visual Order Letter Assignment

_For any_ HTML email input using table-based layout where visual rendering order differs from HTML source order, the fixed pipeline SHALL assign letter labels (A, B, C, ...) based on the visual top-to-bottom Y-position of links as rendered by Playwright, not based on HTML parse order.

**Validates: Requirements 2.5**

Property 4: Bug Condition — Accurate Confidence Metric

_For any_ annotation run, the fixed pipeline SHALL compute confidence as the ratio of successfully-placed badges to total extractable links (all `<a href>` after filtering fonts/mailto/tel/javascript), so that links dropped by the classifier are reflected in a lower confidence score.

**Validates: Requirements 2.6**

Property 5: Preservation — Existing Filtering and Deduplication

_For any_ input where the bug condition does NOT hold (all links have descriptive non-empty anchor text, unique URLs, single-column layout), the fixed pipeline SHALL produce the same result as the original pipeline, preserving font/protocol filtering, same-text deduplication, fallback classification, and sequential letter ordering.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `backend/docker/html_parser.py`

**Function**: `extract_links()`

**Specific Changes**:
1. **Add element index to dedup key for empty anchor text**: When `anchor` is empty, append an incrementing element index to the dedup key so that `(url, "", 0)` and `(url, "", 1)` are treated as distinct entries. When anchor text is non-empty, continue using `(url, anchor.lower())` as before.
2. **Extract image alt text as fallback anchor**: When `tag.get_text(strip=True)` returns empty, check for `<img>` children and use their `alt` attribute as contextual information passed to the classifier. Store this in a new `img_alt` field.
3. **Track element index**: Add an `element_index` field to each link dict for downstream use in visual reordering.

---

**File**: `backend/docker/bedrock_classifier.py`

**Function**: `classify_links()` — system prompt and letter assignment

**Specific Changes**:
1. **Update system prompt**: Add explicit instructions that image-only links (empty anchor text), generic CTA text ("Click here", "Learn more"), and ghost-link overlays are ALL valid user-facing links that should have `include: true`. Only font stylesheets, tracking pixels (1x1 images with no clickable area), and protocol-only links should be excluded.
2. **Include img_alt in classifier payload**: Pass the `img_alt` field (if present) to give the classifier context about image-wrapped links.
3. **Remove letter assignment from classify_links()**: Extract the letter assignment logic into a separate function `assign_letters()` that can be called after visual reordering. The `classify_links()` function should return classified links without letters.

---

**File**: `backend/docker/bedrock_classifier.py` (new function)

**Function**: `assign_letters(classified_links, bboxes)` — new

**Specific Changes**:
1. **Create `assign_letters()` function**: Accept classified links and Playwright bounding boxes. Match each link to its bbox by URL (and anchor text for disambiguation). Sort by `center_y` ascending. Assign letters A, B, C... in visual order.
2. **Fallback to source order**: If no bboxes are available (screenshot service failure), fall back to HTML source order using `element_index`.

---

**File**: `backend/docker/image_annotator.py`

**Function**: `annotate_screenshot()`

**Specific Changes**:
1. **Accept `total_extractable` parameter**: Add an optional `total_extractable: int | None` parameter to `annotate_screenshot()`.
2. **Fix confidence denominator**: When `total_extractable` is provided, compute confidence as `matched_count / total_extractable * 100` instead of `matched_count / total_count * 100`. This ensures links dropped by the classifier reduce the confidence score.

---

**File**: `backend/docker/handler.py`

**Function**: `_handle_process()`

**Specific Changes**:
1. **Pass `raw_links` count to annotator**: After extracting `raw_links`, pass `len(raw_links)` as `total_extractable` to `annotate_screenshot()` so the confidence denominator reflects all extractable links.
2. **Call `assign_letters()` after screenshots**: Move letter assignment to after screenshot capture so bounding box data is available for visual reordering. Call `assign_letters(classified, desktop_bboxes)` before annotation.
3. **Pipeline order adjustment**: The flow becomes: parse → classify (no letters) → screenshot → assign_letters (with bboxes) → annotate → build PDF.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bugs on unfixed code, then verify the fixes work correctly and preserve existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bugs BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write unit tests that exercise each buggy code path with crafted HTML inputs. Run these tests on the UNFIXED code to observe failures and understand the root cause.

**Test Cases**:
1. **Generic Text Filtering Test**: Create HTML with `<a href="https://example.com">Click here</a>` and verify `classify_links()` drops it (will fail on unfixed code — link excluded)
2. **Image-Only Link Filtering Test**: Create HTML with `<a href="https://example.com"><img src="banner.png"></a>` and verify `classify_links()` drops it (will fail on unfixed code — link excluded)
3. **Empty Text Dedup Collision Test**: Create HTML with two `<a href="https://same-url.com"><img src="a.png"></a>` and `<a href="https://same-url.com"><img src="b.png"></a>`, verify `extract_links()` returns only 1 link (will fail on unfixed code — second link dropped)
4. **Source Order vs Visual Order Test**: Create table-based HTML where link at row 2, col 1 appears before link at row 1, col 2 in source but after it visually. Verify letters follow source order (will fail on unfixed code — wrong letter assignment)

**Expected Counterexamples**:
- `classify_links()` returns empty list or reduced list when given image-only/generic-text links
- `extract_links()` returns 1 link instead of 2 for same-URL empty-text links
- Letter assignment follows HTML parse index, not visual Y-position
- Confidence reports 100% when links are missing from classified output

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed functions produce the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  raw_links := extract_links_fixed(input.html)
  classified := classify_links_fixed(raw_links)
  lettered := assign_letters(classified, input.bboxes)
  _, stats := annotate_screenshot_fixed(input.screenshot, lettered, total_extractable=len(raw_links))
  
  ASSERT all user-facing links are in raw_links (no dedup collision)
  ASSERT all non-font/protocol links are in classified (no over-filtering)
  ASSERT letters follow visual Y-order (sorted by center_y)
  ASSERT stats.confidence == matched / len(raw_links) * 100
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed functions produce the same result as the original functions.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT extract_links_original(input) == extract_links_fixed(input)
  ASSERT classify_links_original(input) == classify_links_fixed(input)  -- same labels, same include flags
  ASSERT letter_order_original(input) == letter_order_fixed(input)  -- same A,B,C sequence
  ASSERT confidence_original(input) == confidence_fixed(input)  -- same score
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many HTML inputs with descriptive, unique-text links to verify no regression
- It catches edge cases in dedup logic that manual unit tests might miss
- It provides strong guarantees that single-column, descriptive-text emails produce identical output

**Test Plan**: Observe behavior on UNFIXED code first for well-formed emails (descriptive text, unique URLs, single-column), then write property-based tests capturing that behavior.

**Test Cases**:
1. **Font/Protocol Filtering Preservation**: Verify that `fonts.googleapis.com`, `mailto:`, `tel:`, `javascript:` links continue to be excluded after fix
2. **Same-Text Dedup Preservation**: Verify that two `<a>` tags with same URL and same non-empty anchor text continue to be deduplicated to one
3. **Fallback Classification Preservation**: Verify that when Bedrock is unavailable, all links get generic labels and are included
4. **Single-Column Order Preservation**: Verify that in single-column HTML, letter assignment remains A, B, C in source order (which matches visual order)

### Unit Tests

- Test `extract_links()` with image-wrapped links, ghost-links, and empty anchor text — verify all are extracted
- Test `extract_links()` dedup: same URL + empty text at different positions → both preserved
- Test `extract_links()` dedup: same URL + same non-empty text → still deduplicated to one
- Test `assign_letters()` with mock bboxes in non-sequential Y-order → verify letters follow Y-order
- Test `assign_letters()` fallback with no bboxes → verify source-order assignment
- Test confidence calculation with `total_extractable` > classified count → verify reduced confidence
- Test confidence calculation with `total_extractable` == classified count → verify same as before

### Property-Based Tests

- Generate random HTML with N links having unique descriptive text → verify `extract_links()` returns exactly N links (preservation)
- Generate random HTML with M image-wrapped links sharing K URLs → verify `extract_links()` returns M links, not K (fix)
- Generate random bbox lists with shuffled Y-positions → verify `assign_letters()` always assigns letters in ascending Y-order (fix)
- Generate random classified link lists with varying `total_extractable` values → verify confidence formula correctness (fix)

### Integration Tests

- End-to-end test with Campaign 25-256 HTML (table layout) → verify letter ordering matches visual layout
- End-to-end test with Campaign 26-030 HTML (generic "Click here" CTA) → verify all 4 links detected
- End-to-end test with Campaign 26-026 HTML (image-wrapped duplicate URLs) → verify both image links preserved
- Pipeline test verifying confidence < 100% when classifier drops a link (mocked Bedrock response)
