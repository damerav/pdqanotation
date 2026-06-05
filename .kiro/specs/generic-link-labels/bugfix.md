# Bugfix Requirements Document

## Introduction

The Bedrock link classifier produces generic "Link N" labels (e.g., "Link 9", "Link 10", "Link 11") instead of meaningful, descriptive names for links located in the footer and safety sections of pharma email campaigns. This primarily affects links deep in the HTML where the surrounding context provided to the model is insufficient for it to infer a meaningful label. The bug degrades the usefulness of the annotated PDF output, forcing users to manually identify what each generically-labeled link points to.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the Bedrock model returns fewer classifications than the number of input links THEN the system assigns generic "Link {i+1}" fallback labels to the unmatched trailing links

1.2 WHEN the entire Bedrock classification call fails (exception) THEN the system assigns generic "Link {i+1}" labels to all links

1.3 WHEN the context field provided to the model is truncated to 150 characters and the link appears deep in a long parent element (e.g., footer/safety disclaimer sections) THEN the model receives insufficient surrounding text and returns a generic or unhelpful label such as "Link 9"

1.4 WHEN the Bedrock model itself returns a label matching the pattern "Link N" (where N is a number) THEN the system accepts and uses that generic label without attempting to derive a better one from available link metadata (URL, anchor text, img_alt)

### Expected Behavior (Correct)

2.1 WHEN the Bedrock model returns fewer classifications than the number of input links THEN the system SHALL derive a meaningful fallback label from the link's available metadata (anchor text, URL path, or img_alt) instead of using "Link {i+1}"

2.2 WHEN the entire Bedrock classification call fails THEN the system SHALL derive meaningful fallback labels from each link's available metadata (anchor text, URL path, or img_alt) instead of using "Link {i+1}"

2.3 WHEN a link appears deep in a long parent element THEN the system SHALL provide sufficient surrounding context (more than 150 characters) to the Bedrock model so it can generate a meaningful label

2.4 WHEN the Bedrock model returns a label matching the generic pattern "Link N" THEN the system SHALL attempt to replace it with a meaningful label derived from the link's anchor text, URL domain/path, or img_alt attribute

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the Bedrock model returns a meaningful, non-generic label for a link THEN the system SHALL CONTINUE TO use that model-provided label as-is

3.2 WHEN a link has empty anchor text and no img_alt and an opaque URL THEN the system SHALL CONTINUE TO include the link in the output (with the best available label) rather than dropping it

3.3 WHEN all links are successfully classified by the Bedrock model with meaningful labels THEN the system SHALL CONTINUE TO return those labels without modification

3.4 WHEN the link extraction and deduplication logic in html_parser.py processes links THEN the system SHALL CONTINUE TO extract and deduplicate links using the same rules (URL + anchor text keying, element_index for empty anchors)

3.5 WHEN the assign_letters function assigns letter labels based on visual or source order THEN the system SHALL CONTINUE TO assign letters using the same ordering logic
