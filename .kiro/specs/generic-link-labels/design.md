# Generic Link Labels Bugfix Design

## Overview

The Bedrock link classifier in `bedrock_classifier.py` produces generic "Link N" labels (e.g., "Link 9", "Link 10") instead of meaningful, descriptive names for links in the footer and safety sections of pharma email campaigns. This occurs due to four interrelated causes: insufficient context truncation (150 chars), no post-processing of generic Bedrock responses, and generic fallback labels when Bedrock returns fewer results or fails entirely. The fix introduces a `derive_label_from_metadata` helper, increases the context window, and adds post-processing to ensure every link receives the most descriptive label possible.

## Glossary

- **Bug_Condition (C)**: The condition where a link receives a generic "Link N" label — either from Bedrock's response, from the fallback when Bedrock returns fewer classifications, or from the exception fallback when Bedrock fails entirely
- **Property (P)**: The desired behavior — every link should have a meaningful, descriptive label derived from Bedrock classification or, failing that, from the link's own metadata (anchor text, URL path/domain, img_alt)
- **Preservation**: Existing behavior that must remain unchanged — meaningful Bedrock labels used as-is, link extraction/dedup logic, letter assignment ordering, and inclusion of links with minimal metadata
- **classify_links**: The function in `backend/docker/bedrock_classifier.py` that sends links to Bedrock for classification and returns labeled, filtered links
- **derive_label_from_metadata**: A new helper function that extracts a meaningful label from a link's anchor_text, URL path/domain, or img_alt attribute
- **context**: The surrounding HTML text sent to Bedrock for each link, currently truncated to 150 characters

## Bug Details

### Bug Condition

The bug manifests when the `classify_links` function produces generic "Link N" labels for links. This happens through four distinct code paths:

1. Bedrock returns fewer classifications than input links → trailing links get "Link {i+1}"
2. Bedrock call raises an exception → all links get "Link {i+1}"
3. Context truncated to 150 chars → Bedrock receives insufficient text for footer/safety links and returns unhelpful labels
4. Bedrock itself returns a "Link N" pattern → system accepts it without attempting a better label

**Formal Specification:**
```
FUNCTION isBugCondition(link, classifications, bedrock_failed)
  INPUT: link of type dict, classifications of type list, bedrock_failed of type boolean
  OUTPUT: boolean

  link_index := indexOf(link, input_links)

  // Path 1: Bedrock returned fewer results than input links
  IF NOT bedrock_failed AND link_index >= len(classifications) THEN
    RETURN TRUE
  END IF

  // Path 2: Bedrock call failed entirely
  IF bedrock_failed THEN
    RETURN TRUE
  END IF

  // Path 3: Context too short for deep links (indirect — causes Path 4)
  // Path 4: Bedrock returned a generic "Link N" pattern label
  IF NOT bedrock_failed AND link_index < len(classifications) THEN
    label := classifications[link_index].label
    IF label MATCHES regex "^Link\s+\d+$" THEN
      RETURN TRUE
    END IF
  END IF

  RETURN FALSE
END FUNCTION
```

### Examples

- **Footer link with 150-char context**: A "Privacy Policy" link deep in a footer `<td>` has a parent element with 800+ characters of text. Truncated to 150 chars, the context sent to Bedrock is just boilerplate from the top of the parent, missing the "Privacy Policy" anchor text entirely. Bedrock returns "Link 9". Expected: "Privacy Policy" (from anchor text).
- **Safety section link**: An ISI (Important Safety Information) link at position 12 in a 15-link email. Bedrock returns only 10 classifications. The link gets "Link 12". Expected: "Important Safety Information" (from anchor text or URL path).
- **Bedrock timeout**: The Bedrock API times out. All 15 links get "Link 1" through "Link 15". Expected: Each link gets a label derived from its anchor text (e.g., "Prescribing Information"), URL path (e.g., "example.com/safety" → "Safety"), or img_alt.
- **Image link with alt text**: An `<a>` wrapping an `<img alt="Company Logo">` with no anchor text. Bedrock returns "Link 3". Expected: "Company Logo" (from img_alt).

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- When Bedrock returns a meaningful, non-generic label (e.g., "Privacy Policy", "Unsubscribe"), that label must be used as-is without modification
- Links with empty anchor text, no img_alt, and opaque URLs must still be included in the output with the best available label
- When all links are successfully classified by Bedrock with meaningful labels, the output must be identical to current behavior
- Link extraction and deduplication logic in `html_parser.py` must remain unchanged
- Letter assignment via `assign_letters()` must continue using the same visual/source ordering logic

**Scope:**
All inputs where Bedrock returns meaningful (non-"Link N") labels for all links and the classification count matches the input count are completely unaffected by this fix. This includes:
- Emails with few links where Bedrock reliably classifies all of them
- Links with rich surrounding context that Bedrock can interpret
- Any link where Bedrock returns a descriptive label

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Insufficient Context Truncation**: In `_build_link_payload()`, the context field is truncated to 150 characters (`l["context"][:150]`). For links deep in long parent elements (footer disclaimers, safety sections), the first 150 characters of the parent text are generic boilerplate that doesn't help Bedrock identify the specific link. The meaningful text surrounding the link is cut off.

2. **No Metadata-Based Fallback**: When Bedrock returns fewer classifications than input links (line: `clf = classifications[i] if i < len(classifications) else {"label": f"Link {i+1}", "include": True}`), the fallback is a generic "Link {i+1}" label. The system has access to anchor_text, URL, and img_alt but doesn't use them.

3. **No Exception Fallback Using Metadata**: When the entire Bedrock call fails (the `except` block), the fallback generates `{"label": f"Link {i+1}", "include": True}` for all links. Again, available metadata is ignored.

4. **No Post-Processing of Generic Bedrock Labels**: When Bedrock itself returns a "Link N" pattern (because it couldn't determine a better label from the truncated context), the system accepts it verbatim. There is no check to see if the link's own metadata could provide a better label.

## Correctness Properties

Property 1: Bug Condition - Metadata-Derived Labels Replace Generic Fallbacks

_For any_ input where the bug condition holds (Bedrock returns fewer results, Bedrock fails, or Bedrock returns a "Link N" pattern label) AND the link has non-empty metadata (anchor_text, URL path, or img_alt), the fixed `classify_links` function SHALL produce a label derived from that metadata rather than a generic "Link N" pattern.

**Validates: Requirements 2.1, 2.2, 2.4**

Property 2: Preservation - Meaningful Bedrock Labels Unchanged

_For any_ input where the bug condition does NOT hold (Bedrock returns a meaningful, non-"Link N" label for every link and the classification count matches the input count), the fixed `classify_links` function SHALL produce exactly the same labels as the original function, preserving all meaningful Bedrock classifications.

**Validates: Requirements 3.1, 3.3**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `backend/docker/bedrock_classifier.py`

**Function**: `classify_links` and new helper `derive_label_from_metadata`

**Specific Changes**:

1. **Add `derive_label_from_metadata` helper**: A new function that takes a link dict and returns a meaningful label by checking, in priority order:
   - `anchor_text` — if non-empty and not purely whitespace, use it (truncated to ~60 chars)
   - `img_alt` — if present and non-empty, use it
   - URL path — extract the last meaningful path segment from the URL, title-case it, replace hyphens/underscores with spaces (e.g., `https://example.com/prescribing-information` → "Prescribing Information")
   - URL domain — if the path is empty or just "/", use the domain name (e.g., `https://safety.example.com` → "safety.example.com")
   - Final fallback — if all of the above are empty/opaque, return `"Link {i+1}"` as a last resort

2. **Increase context truncation from 150 to 500 characters**: In `_build_link_payload()`, change `l["context"][:150]` to `l["context"][:500]`. This gives Bedrock more surrounding text for links deep in long parent elements, improving its ability to generate meaningful labels.

3. **Post-process Bedrock results to replace "Link N" patterns**: After parsing the Bedrock response, iterate over the classifications and check each label against the regex `^Link\s+\d+$`. If it matches, replace it with the result of `derive_label_from_metadata(raw_links[i])`.

4. **Use metadata-derived labels in the partial-result fallback**: Replace the inline `{"label": f"Link {i+1}", "include": True}` fallback (for when `i >= len(classifications)`) with `{"label": derive_label_from_metadata(raw_links[i]), "include": True}`.

5. **Use metadata-derived labels in the exception fallback**: Replace the exception handler's `{"label": f"Link {i+1}", "include": True}` with `{"label": derive_label_from_metadata(link), "include": True}` for each link.

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that mock Bedrock to return fewer results, raise exceptions, or return "Link N" labels, then assert that the output labels are NOT generic "Link N" patterns when metadata is available. Run these tests on the UNFIXED code to observe failures and understand the root cause.

**Test Cases**:
1. **Partial Bedrock Response Test**: Mock Bedrock to return 3 classifications for 5 input links. Links 4-5 have anchor_text. Assert labels are metadata-derived, not "Link 4"/"Link 5" (will fail on unfixed code)
2. **Bedrock Failure Test**: Mock Bedrock to raise an exception. All links have anchor_text. Assert no label matches "Link N" pattern (will fail on unfixed code)
3. **Generic Bedrock Label Test**: Mock Bedrock to return "Link 9" for a link with anchor_text="Privacy Policy". Assert label is "Privacy Policy", not "Link 9" (will fail on unfixed code)
4. **Context Length Test**: Verify that the payload sent to Bedrock includes up to 500 chars of context, not 150 (will fail on unfixed code)

**Expected Counterexamples**:
- Links with rich metadata (anchor_text, img_alt, descriptive URLs) still receive "Link N" labels
- Possible causes: no metadata fallback logic, no post-processing of generic Bedrock labels, context truncation too aggressive

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL link WHERE isBugCondition(link, classifications, bedrock_failed) DO
  result_label := classify_links_fixed(raw_links)[indexOf(link)]
  IF link.anchor_text IS NOT EMPTY THEN
    ASSERT result_label == link.anchor_text (or derived from it)
  ELSE IF link.img_alt IS NOT EMPTY THEN
    ASSERT result_label == link.img_alt
  ELSE IF link.url HAS meaningful path THEN
    ASSERT result_label IS derived from URL path
  END IF
  ASSERT result_label DOES NOT MATCH regex "^Link\s+\d+$"
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(link, classifications, bedrock_failed) DO
  ASSERT classify_links_original(input) = classify_links_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for inputs where Bedrock returns meaningful labels for all links, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Meaningful Label Preservation**: Mock Bedrock to return descriptive labels for all links. Verify the output labels match Bedrock's response exactly
2. **Include/Exclude Preservation**: Mock Bedrock to return include:false for some links. Verify those links are still excluded from the output
3. **Link Order Preservation**: Verify that the order of links in the output matches the order of included links from Bedrock's response

### Unit Tests

- Test `derive_label_from_metadata` with anchor_text present → returns anchor_text
- Test `derive_label_from_metadata` with empty anchor_text but img_alt present → returns img_alt
- Test `derive_label_from_metadata` with empty anchor_text and img_alt but descriptive URL → returns URL-derived label
- Test `derive_label_from_metadata` with opaque URL and no metadata → returns "Link N" fallback
- Test context truncation is 500 characters in the payload sent to Bedrock
- Test that "Link N" pattern regex correctly matches "Link 1", "Link 10", "Link 123" but not "Link to Privacy Policy"

### Property-Based Tests

- Generate random link metadata combinations (anchor_text, img_alt, URL paths) and verify `derive_label_from_metadata` always returns a non-empty string
- Generate random link lists, mock Bedrock to return fewer results, and verify no output label matches "Link N" when metadata is available
- Generate random link lists with meaningful Bedrock labels and verify output is unchanged (preservation)

### Integration Tests

- Test full `classify_links` flow with a mix of well-classified and under-classified links
- Test that the pipeline in `handler.py` continues to work end-to-end with the updated `classify_links`
- Test that links in footer/safety sections with long parent context receive meaningful labels
