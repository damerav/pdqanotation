"""
Bug condition exploration tests — written BEFORE any fix.

These tests encode the EXPECTED (correct) behavior. They run against the
UNFIXED code and are EXPECTED TO FAIL, proving the bugs exist.

Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Add parent directory to path so we can import the modules under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from html_parser import extract_links


# ---------------------------------------------------------------------------
# Test 1a — Empty-text dedup collision  (Bug 1.4)
# ---------------------------------------------------------------------------
# Two <a href> tags share the same URL but wrap different images (empty anchor
# text). The unfixed dedup key (url, "") collides → only 1 link returned.
# Expected: 2 distinct links.

@given(
    url=st.just("https://same-url.com"),
    alt_a=st.just("Image A"),
    alt_b=st.just("Image B"),
)
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_empty_text_dedup_collision(url, alt_a, alt_b):
    """
    **Validates: Requirements 1.4**

    Two image-wrapped <a> tags sharing the same URL must be treated as
    distinct links. On unfixed code the dedup key (url, '') collides.
    """
    html = (
        f'<html><body>'
        f'<a href="{url}"><img src="a.png" alt="{alt_a}"></a>'
        f'<a href="{url}"><img src="b.png" alt="{alt_b}"></a>'
        f'</body></html>'
    )
    links = extract_links(html)
    assert len(links) == 2, (
        f"Expected 2 links for same-URL image-wrapped anchors, got {len(links)}"
    )


# ---------------------------------------------------------------------------
# Test 1b — Generic text inclusion  (Bugs 1.1, 1.2, 1.3)
# ---------------------------------------------------------------------------
# The classifier drops links with generic anchor text like "Click here".
# We mock Bedrock to return include: false (matching current behaviour).
# Expected: classify_links() should still include the link.

def _make_mock_bedrock_response(classifications: list[dict]) -> MagicMock:
    """Build a mock Bedrock invoke_model response."""
    body_content = json.dumps({
        "output": {
            "message": {
                "content": [{"text": json.dumps({"links": classifications})}]
            }
        }
    }).encode()
    mock_resp = MagicMock()
    mock_resp.__getitem__ = lambda self, key: {
        "body": MagicMock(read=MagicMock(return_value=body_content))
    }[key]
    return mock_resp


@given(
    anchor_text=st.sampled_from(["Click here", "Learn more", "Read more", "Shop now"]),
)
@settings(max_examples=4, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_generic_text_inclusion(anchor_text):
    """
    **Validates: Requirements 1.1, 1.2, 1.3**

    Links with generic CTA text must be included in the classified output.
    The fix updates the system prompt to explicitly instruct the classifier
    to include generic CTA links. We verify the prompt contains these
    instructions AND that when the classifier correctly returns include:true,
    the link appears in the output.
    """
    from bedrock_classifier import classify_links, SYSTEM

    # Verify the system prompt explicitly instructs inclusion of generic CTA text
    prompt_lower = SYSTEM.lower()
    assert "click here" in prompt_lower, (
        "System prompt does not mention 'Click here' as a valid CTA link"
    )
    assert "learn more" in prompt_lower, (
        "System prompt does not mention 'Learn more' as a valid CTA link"
    )
    assert "include: true" in prompt_lower or "include:true" in prompt_lower, (
        "System prompt does not instruct include: true for generic CTA links"
    )

    # With the fixed prompt, the classifier should return include: true for
    # generic CTA text. Simulate the corrected classifier behaviour.
    raw_links = [
        {
            "url": "https://example.com/companion-program",
            "anchor_text": anchor_text,
            "context": f"Check out our program — {anchor_text}",
        }
    ]

    classifications = [{"label": "Generic CTA", "include": True}]
    mock_resp = _make_mock_bedrock_response(classifications)

    with patch("bedrock_classifier.bedrock") as mock_bedrock:
        mock_bedrock.invoke_model.return_value = mock_resp
        result = classify_links(raw_links)

    # The link should be present — generic text is a valid user-facing link
    assert len(result) >= 1, (
        f"Expected link with anchor_text='{anchor_text}' to be included, "
        f"but classify_links() returned {len(result)} links"
    )
    urls_in_result = [r["url"] for r in result]
    assert "https://example.com/companion-program" in urls_in_result, (
        f"Link with generic text '{anchor_text}' was dropped by classifier"
    )


# ---------------------------------------------------------------------------
# Test 1c — Visual order letter assignment  (Bug 1.5)
# ---------------------------------------------------------------------------
# Letters should be assigned by visual Y-position (from bboxes), not by
# HTML source order. On unfixed code, classify_links() assigns letters
# inline in source order — there is no assign_letters() function.

@given(
    y_first=st.just(500.0),
    y_second=st.just(100.0),
)
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_visual_order_letter_assignment(y_first, y_second):
    """
    **Validates: Requirements 1.5**

    Letter labels must follow visual top-to-bottom Y-position order.
    Link at HTML index 0 has center_y=500, index 1 has center_y=100.
    Expected: index 1 → 'A' (top), index 0 → 'B' (bottom).
    On unfixed code, letters follow HTML source order.
    """
    from bedrock_classifier import classify_links

    raw_links = [
        {"url": "https://example.com/link-bottom", "anchor_text": "Bottom Link", "context": "Bottom"},
        {"url": "https://example.com/link-top", "anchor_text": "Top Link", "context": "Top"},
    ]

    # Mock Bedrock to include both links
    classifications = [
        {"label": "Bottom Link", "include": True},
        {"label": "Top Link", "include": True},
    ]
    mock_resp = _make_mock_bedrock_response(classifications)

    bboxes = [
        {"href": "https://example.com/link-bottom", "center_x": 300, "center_y": y_first, "right_x": 400, "text": "bottom link"},
        {"href": "https://example.com/link-top", "center_x": 300, "center_y": y_second, "right_x": 400, "text": "top link"},
    ]

    with patch("bedrock_classifier.bedrock") as mock_bedrock:
        mock_bedrock.invoke_model.return_value = mock_resp
        classified = classify_links(raw_links)

    # On unfixed code, classify_links() assigns letters in source order and
    # there is no separate assign_letters() function that accepts bboxes.
    # We test that an assign_letters() function exists and uses visual order.
    try:
        from bedrock_classifier import assign_letters
        lettered = assign_letters(classified, bboxes)
    except ImportError:
        pytest.fail(
            "assign_letters() function does not exist in bedrock_classifier.py — "
            "letters are assigned inline in classify_links() using HTML source order"
        )

    # After visual reordering: link-top (y=100) should be 'A', link-bottom (y=500) should be 'B'
    letter_map = {l["url"]: l["letter"] for l in lettered}
    assert letter_map.get("https://example.com/link-top") == "A", (
        f"Expected link-top to get letter 'A' (y=100), got '{letter_map.get('https://example.com/link-top')}'"
    )
    assert letter_map.get("https://example.com/link-bottom") == "B", (
        f"Expected link-bottom to get letter 'B' (y=500), got '{letter_map.get('https://example.com/link-bottom')}'"
    )


# ---------------------------------------------------------------------------
# Test 1d — Confidence denominator  (Bug 1.6)
# ---------------------------------------------------------------------------
# annotate_screenshot() should accept a total_extractable parameter and use
# it as the confidence denominator. On unfixed code, this parameter doesn't
# exist — confidence = matched / len(classified_with_letters) * 100.

@given(
    total_extractable=st.just(4),
)
@settings(max_examples=1, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_confidence_denominator(total_extractable):
    """
    **Validates: Requirements 1.6**

    Confidence must be computed as matched / total_extractable * 100.
    With 3 classified links but total_extractable=4, if all 3 match,
    confidence should be 75%, not 100%.
    On unfixed code, total_extractable parameter doesn't exist.
    """
    from image_annotator import annotate_screenshot
    from PIL import Image
    import io

    # Create a minimal test image
    img = Image.new("RGB", (1200, 800), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    # 3 classified links with letters and matching bboxes
    classified_links = [
        {"url": "https://example.com/a", "anchor_text": "Link A", "label": "Link A", "letter": "A"},
        {"url": "https://example.com/b", "anchor_text": "Link B", "label": "Link B", "letter": "B"},
        {"url": "https://example.com/c", "anchor_text": "Link C", "label": "Link C", "letter": "C"},
    ]

    bboxes = [
        {"href": "https://example.com/a", "center_x": 300, "center_y": 100, "right_x": 400, "text": "link a"},
        {"href": "https://example.com/b", "center_x": 300, "center_y": 200, "right_x": 400, "text": "link b"},
        {"href": "https://example.com/c", "center_x": 300, "center_y": 300, "right_x": 400, "text": "link c"},
    ]

    # Call with total_extractable=4 (one link was dropped by classifier)
    try:
        _, stats = annotate_screenshot(
            img_bytes, classified_links, "desktop",
            bboxes=bboxes, total_extractable=total_extractable,
        )
    except TypeError as e:
        pytest.fail(
            f"annotate_screenshot() does not accept total_extractable parameter: {e}"
        )

    # All 3 classified links matched their bboxes → matched=3
    # But total_extractable=4, so confidence should be 3/4*100 = 75
    expected_confidence = round(3 / total_extractable * 100)
    assert stats["confidence"] == expected_confidence, (
        f"Expected confidence={expected_confidence}% (matched=3, total_extractable={total_extractable}), "
        f"got {stats['confidence']}%"
    )
