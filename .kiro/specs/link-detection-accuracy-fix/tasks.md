# Implementation Plan

- [x] 1. Write bug condition exploration tests
  - **Property 1: Bug Condition** - Link Detection and Dedup Failures
  - **CRITICAL**: Write these property-based tests BEFORE implementing the fix
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **NOTE**: These tests encode the expected behavior — they will validate the fix when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate the bugs exist on unfixed code
  - **Scoped PBT Approach**: Scope properties to concrete failing cases for reproducibility
  - Test 1a — Empty-text dedup collision: Create HTML with two `<a href="https://same-url.com"><img src="a.png" alt="Image A"></a>` and `<a href="https://same-url.com"><img src="b.png" alt="Image B"></a>`. Assert `extract_links()` returns 2 links. On unfixed code, dedup key `(url, "")` collides and only 1 is returned — test FAILS (confirms bug 1.4 exists)
  - Test 1b — Generic text inclusion: Create a list of raw links including one with `anchor_text="Click here"` and a valid non-tracking URL. Mock Bedrock to return `include: false` for it (matching current classifier behavior). Assert `classify_links()` includes it in the result. On unfixed code, the classifier drops it — test FAILS (confirms bugs 1.1, 1.2, 1.3 exist)
  - Test 1c — Visual order letter assignment: Create classified links and mock bboxes where link at HTML index 0 has `center_y=500` and link at HTML index 1 has `center_y=100`. Assert letters are assigned by ascending Y-position (index 1 gets "A", index 0 gets "B"). On unfixed code, `classify_links()` assigns letters in HTML source order — test FAILS (confirms bug 1.5 exists)
  - Test 1d — Confidence denominator: Call `annotate_screenshot()` with 3 classified links but `total_extractable=4`. Assert confidence is `matched/4 * 100`, not `matched/3 * 100`. On unfixed code, `total_extractable` parameter doesn't exist — test FAILS (confirms bug 1.6 exists)
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct — it proves the bugs exist)
  - Document counterexamples found to understand root causes
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Filtering, Dedup, and Ordering Behavior
  - **IMPORTANT**: Follow observation-first methodology — run UNFIXED code, observe outputs, then write tests asserting those outputs
  - Observe: `extract_links()` on HTML with `fonts.googleapis.com`, `mailto:`, `tel:`, `javascript:` links returns empty list (all filtered)
  - Observe: `extract_links()` on HTML with two `<a href="https://example.com">Same Text</a>` returns 1 link (same-URL same-text dedup works)
  - Observe: `extract_links()` on HTML with N links having unique descriptive text and unique URLs returns exactly N links
  - Observe: `classify_links()` fallback when Bedrock raises an exception returns all links with generic labels "Link 1", "Link 2", etc.
  - Observe: In single-column HTML where source order matches visual order, letter assignment is sequential A, B, C
  - Write property-based tests: for all HTML inputs with unique descriptive anchor text and unique URLs (non-buggy inputs), `extract_links()` returns exactly the expected count
  - Write property-based tests: for all inputs with font/mailto/tel/javascript URLs, those links are excluded
  - Write property-based tests: for all inputs with same URL and same non-empty anchor text, dedup reduces to one instance
  - Verify all tests PASS on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix link detection accuracy across the pipeline

  - [x] 3.1 Fix deduplication key and add element index in `html_parser.py`
    - In `extract_links()`, add an incrementing `element_index` counter for each `<a>` tag processed
    - When `anchor` is empty, change dedup key from `(url, anchor.lower())` to `(url, anchor.lower(), element_index)` so that image-wrapped links sharing the same URL are treated as distinct
    - When `anchor` is non-empty, continue using `(url, anchor.lower())` as the dedup key (preserves requirement 3.2)
    - Extract `<img>` child `alt` attribute as `img_alt` field when anchor text is empty, to provide context to the classifier
    - Include `element_index` in each link dict for downstream visual reordering
    - _Bug_Condition: isBugCondition(input) where two+ `<a>` tags share same URL with empty anchor text — dedup key `(url, "")` collides_
    - _Expected_Behavior: All visually distinct `<a>` elements preserved with unique dedup keys_
    - _Preservation: Same-URL same-non-empty-text links still deduplicated; font/mailto/tel/javascript filtering unchanged_
    - _Requirements: 2.4, 3.1, 3.2_

  - [x] 3.2 Update classifier system prompt and payload in `bedrock_classifier.py`
    - Update `SYSTEM` prompt to explicitly instruct that image-only links (empty anchor text), generic CTA text ("Click here", "Learn more", "Read more", "Shop now"), and ghost-link CSS overlays are ALL valid user-facing links with `include: true`
    - Add explicit instruction that ONLY font stylesheets, 1x1 tracking pixels with no clickable area, and protocol-only links should be `include: false`
    - Include `img_alt` field in the classifier payload when present, so the model has context about image-wrapped links
    - _Bug_Condition: Classifier marks valid links as include:false due to empty/generic anchor text or ghost-link class_
    - _Expected_Behavior: All user-facing links classified as include:true regardless of anchor text content_
    - _Preservation: Font stylesheets and tracking pixels still excluded; descriptive-text links still labeled correctly_
    - _Requirements: 2.1, 2.2, 2.3, 3.3, 3.4_

  - [x] 3.3 Extract letter assignment into `assign_letters()` function in `bedrock_classifier.py`
    - Remove letter assignment logic from `classify_links()` — it should return classified links WITHOUT letters
    - Create new `assign_letters(classified_links, bboxes=None)` function that:
      - Accepts classified links and optional Playwright bounding boxes
      - When bboxes are provided: match each link to its bbox by URL (and anchor text for disambiguation), sort by `center_y` ascending, assign letters A, B, C... in visual order
      - When bboxes are not available: fall back to source order using `element_index`, assign letters sequentially
    - _Bug_Condition: Letters assigned in HTML source order instead of visual rendering order for table-based layouts_
    - _Expected_Behavior: Letters follow visual top-to-bottom Y-position from Playwright bboxes_
    - _Preservation: Single-column layouts where source order == visual order get same sequential letters_
    - _Requirements: 2.5, 3.5_

  - [x] 3.4 Fix confidence denominator in `image_annotator.py`
    - Add optional `total_extractable: int | None = None` parameter to `annotate_screenshot()`
    - When `total_extractable` is provided and > 0, compute confidence as `matched_count / total_extractable * 100` instead of `matched_count / total_count * 100`
    - When `total_extractable` is not provided, fall back to existing behavior (`matched_count / total_count * 100`)
    - _Bug_Condition: Confidence denominator uses classified link count, masking missed links_
    - _Expected_Behavior: Confidence = matched / total_extractable * 100, reflecting all extractable links_
    - _Preservation: When total_extractable == total_count, confidence is identical to before_
    - _Requirements: 2.6_

  - [x] 3.5 Adjust pipeline order in `handler.py`
    - Update `_handle_process()` to follow new pipeline order: parse → classify (no letters) → screenshot → assign_letters (with desktop bboxes) → annotate → build PDF
    - Import `assign_letters` from `bedrock_classifier`
    - After `classify_links(raw_links)` returns (now without letters), capture screenshots to get `desktop_bboxes`
    - Call `assign_letters(classified, desktop_bboxes)` to assign letters in visual order
    - Pass `total_extractable=len(raw_links)` to both `annotate_screenshot()` calls so confidence reflects all extractable links
    - _Bug_Condition: Letter assignment happens before bboxes are available; confidence denominator is wrong_
    - _Expected_Behavior: Letters assigned after screenshot using visual order; confidence uses total extractable count_
    - _Preservation: Pipeline still produces PDF, sends email, stores to S3 — all downstream behavior unchanged_
    - _Requirements: 2.5, 2.6, 3.5_

  - [x] 3.6 Verify bug condition exploration tests now pass
    - **Property 1: Expected Behavior** - Link Detection and Dedup Fixes Validated
    - **IMPORTANT**: Re-run the SAME tests from task 1 — do NOT write new tests
    - The tests from task 1 encode the expected behavior for all four bug conditions
    - When these tests pass, it confirms: empty-text links are no longer deduplicated incorrectly, generic-text links are included, letters follow visual order, and confidence uses total extractable count
    - Run bug condition exploration tests from step 1
    - **EXPECTED OUTCOME**: Tests PASS (confirms all four bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 3.7 Verify preservation tests still pass
    - **Property 2: Preservation** - No Regressions in Existing Behavior
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm font/mailto/tel/javascript filtering still works, same-text dedup still works, fallback classification still works, single-column ordering still works
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 4. Checkpoint — Ensure all tests pass
  - Run the full test suite (exploration tests, preservation tests, any existing tests)
  - Verify all tests pass with no failures or regressions
  - Ask the user if questions arise or if integration testing against real campaign HTML is needed
