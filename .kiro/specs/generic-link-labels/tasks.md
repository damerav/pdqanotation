# Tasks

## Task 1: Add `derive_label_from_metadata` helper function
- [x] 1.1 Create `derive_label_from_metadata(link: dict, index: int = 0) -> str` function in `backend/docker/bedrock_classifier.py` that returns a meaningful label from link metadata
- [x] 1.2 Implement priority order: anchor_text (non-empty, stripped, truncated to 60 chars) → img_alt → URL path segment (title-cased, hyphens/underscores replaced with spaces) → URL domain → "Link {index+1}" as last resort
- [x] 1.3 Add `_is_generic_label(label: str) -> bool` helper that returns True if label matches regex `^Link\s+\d+$`

## Task 2: Increase context truncation limit
- [x] 2.1 In `_build_link_payload()`, change `l["context"][:150]` to `l["context"][:500]`

## Task 3: Post-process Bedrock results to replace generic labels
- [x] 3.1 After parsing Bedrock classifications, iterate over results and replace any label where `_is_generic_label(label)` returns True with `derive_label_from_metadata(raw_links[i], i)`

## Task 4: Update fallback labels to use metadata
- [x] 4.1 In the partial-result fallback (when `i >= len(classifications)`), replace `{"label": f"Link {i+1}", "include": True}` with `{"label": derive_label_from_metadata(raw_links[i], i), "include": True}`
- [x] 4.2 In the exception fallback (`except` block), replace `{"label": f"Link {i+1}", "include": True}` with `{"label": derive_label_from_metadata(link, i), "include": True}` for each link

## Task 5: Write bug condition exploration tests
- [x] 5.1 [PBT-exploration] Write property-based test: for random links with non-empty anchor_text, when Bedrock returns fewer classifications, assert output labels are NOT "Link N" patterns — expected to FAIL on unfixed code
  - Property: Property 1: Bug Condition - Metadata-Derived Labels Replace Generic Fallbacks
- [x] 5.2 [PBT-exploration] Write property-based test: for random links with metadata, when Bedrock raises an exception, assert no output label matches "Link N" pattern — expected to FAIL on unfixed code
  - Property: Property 1: Bug Condition - Metadata-Derived Labels Replace Generic Fallbacks
- [x] 5.3 [PBT-exploration] Write property-based test: for random links with anchor_text, when Bedrock returns "Link N" labels, assert output labels use anchor_text instead — expected to FAIL on unfixed code
  - Property: Property 1: Bug Condition - Metadata-Derived Labels Replace Generic Fallbacks

## Task 6: Write fix verification tests
- [x] 6.1 Write unit tests for `derive_label_from_metadata`: anchor_text priority, img_alt fallback, URL path extraction, domain fallback, and last-resort "Link N"
- [x] 6.2 Write unit test for `_is_generic_label`: matches "Link 1", "Link 10", "Link 123", does not match "Link to Privacy Policy", "Privacy Link", ""
- [x] 6.3 Write unit test verifying context truncation is 500 characters in the Bedrock payload

## Task 7: Write preservation tests
- [x] 7.1 [PBT-preservation] Write property-based test: for random links where Bedrock returns meaningful (non-"Link N") labels for all links, assert output labels are identical to Bedrock's response
  - Property: Property 2: Preservation - Meaningful Bedrock Labels Unchanged
- [x] 7.2 [PBT-preservation] Write property-based test: for random links where Bedrock returns include:false, assert those links are excluded from output (same as original behavior)
  - Property: Property 2: Preservation - Meaningful Bedrock Labels Unchanged
