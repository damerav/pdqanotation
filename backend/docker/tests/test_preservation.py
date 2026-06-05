"""
Preservation property tests — written BEFORE any fix.

These tests capture the CURRENT behavior of the unfixed code for non-buggy
inputs. They must ALL PASS on the unfixed code, establishing a baseline
that must be preserved after the fix is applied.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck, assume
from hypothesis import strategies as st

# Add parent directory to path so we can import the modules under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from html_parser import extract_links


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# Strategy: generate a safe descriptive anchor text (no empty, no generic)
_descriptive_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs"), min_codepoint=65, max_codepoint=122),
    min_size=5,
    max_size=30,
).filter(lambda t: t.strip() and t.strip().lower() not in {
    "click here", "learn more", "read more", "shop now", "",
})

# Strategy: generate a safe unique URL path segment
_url_segment = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=4,
    max_size=12,
)


# ---------------------------------------------------------------------------
# Test 2.1 — Font/Protocol Filtering Preservation  (Requirement 3.1)
# ---------------------------------------------------------------------------

@given(
    font_url=st.sampled_from([
        "https://fonts.googleapis.com/css?family=Roboto",
        "https://fonts.gstatic.com/s/roboto/v30/font.woff2",
    ]),
    mailto_addr=st.from_regex(r"[a-z]{3,8}@example\.com", fullmatch=True),
    tel_number=st.from_regex(r"\+1[0-9]{10}", fullmatch=True),
    js_code=st.sampled_from(["javascript:void(0)", "javascript:alert(1)"]),
)
@settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
def test_font_protocol_filtering_preservation(font_url, mailto_addr, tel_number, js_code):
    """
    **Validates: Requirements 3.1**

    Links to font stylesheets, mailto:, tel:, and javascript: protocols
    must be excluded from extract_links() output. This is existing behavior
    that must be preserved after the fix.
    """
    html = (
        f'<html><body>'
        f'<a href="{font_url}">Font</a>'
        f'<a href="mailto:{mailto_addr}">Email Us</a>'
        f'<a href="tel:{tel_number}">Call Us</a>'
        f'<a href="{js_code}">Do Something</a>'
        f'</body></html>'
    )
    links = extract_links(html)
    assert len(links) == 0, (
        f"Expected 0 links (all filtered), got {len(links)}: "
        f"{[l['url'] for l in links]}"
    )


# ---------------------------------------------------------------------------
# Test 2.2 — Same-Text Dedup Preservation  (Requirement 3.2)
# ---------------------------------------------------------------------------

@given(
    anchor=_descriptive_text,
    url_path=_url_segment,
)
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
def test_same_text_dedup_preservation(anchor, url_path):
    """
    **Validates: Requirements 3.2**

    Two <a> tags with the same URL and the same non-empty anchor text must
    be deduplicated to one instance. This is existing behavior that must be
    preserved after the fix.
    """
    url = f"https://example.com/{url_path}"
    html = (
        f'<html><body>'
        f'<a href="{url}">{anchor}</a>'
        f'<a href="{url}">{anchor}</a>'
        f'</body></html>'
    )
    links = extract_links(html)
    assert len(links) == 1, (
        f"Expected 1 link after same-text dedup, got {len(links)}"
    )
    assert links[0]["url"] == url
    assert links[0]["anchor_text"] == anchor


# ---------------------------------------------------------------------------
# Test 2.3 — Unique Links Preservation  (Requirement 3.4)
# ---------------------------------------------------------------------------

@given(
    n=st.integers(min_value=1, max_value=10),
    data=st.data(),
)
@settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
def test_unique_links_preservation(n, data):
    """
    **Validates: Requirements 3.4**

    For HTML with N links having unique descriptive anchor text and unique
    URLs (non-buggy inputs), extract_links() returns exactly N links.
    This is existing behavior that must be preserved.
    """
    # Generate N unique URL segments and N unique anchor texts
    segments = data.draw(
        st.lists(_url_segment, min_size=n, max_size=n, unique=True),
        label="url_segments",
    )
    anchors = data.draw(
        st.lists(_descriptive_text, min_size=n, max_size=n, unique_by=lambda t: t.strip().lower()),
        label="anchors",
    )

    link_tags = "".join(
        f'<a href="https://example.com/{seg}">{anc}</a>'
        for seg, anc in zip(segments, anchors)
    )
    html = f"<html><body>{link_tags}</body></html>"

    links = extract_links(html)
    assert len(links) == n, (
        f"Expected {n} unique links, got {len(links)}"
    )


# ---------------------------------------------------------------------------
# Test 2.4 — Fallback Classification Preservation  (Requirement 3.3)
# ---------------------------------------------------------------------------

@given(
    n=st.integers(min_value=1, max_value=5),
    data=st.data(),
)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
def test_fallback_classification_preservation(n, data):
    """
    **Validates: Requirements 3.3 (superseded by generic-link-labels bugfix req 2.2)**

    When Bedrock raises an exception, classify_links() still includes every
    link, but now derives a meaningful label from each link's metadata
    (anchor_text / URL / img_alt) instead of a generic "Link N" fallback.
    See the generic-link-labels bugfix for the behavior change.
    """
    import re as _re
    from bedrock_classifier import classify_links, derive_label_from_metadata

    segments = data.draw(
        st.lists(_url_segment, min_size=n, max_size=n, unique=True),
        label="url_segments",
    )
    anchors = data.draw(
        st.lists(_descriptive_text, min_size=n, max_size=n, unique_by=lambda t: t.strip().lower()),
        label="anchors",
    )

    raw_links = [
        {
            "url": f"https://example.com/{seg}",
            "anchor_text": anc,
            "context": f"Context for {anc}",
        }
        for seg, anc in zip(segments, anchors)
    ]

    # Mock Bedrock to raise an exception (service unavailable)
    with patch("bedrock_classifier.bedrock") as mock_bedrock:
        mock_bedrock.invoke_model.side_effect = Exception("Service unavailable")
        result = classify_links(raw_links)

    # All links should be included, with meaningful metadata-derived labels —
    # NOT generic "Link N" — since anchor_text metadata is available.
    assert len(result) == n, (
        f"Expected {n} links in fallback, got {len(result)}"
    )
    for i, link in enumerate(result):
        expected = derive_label_from_metadata(raw_links[i], i)
        assert link["label"] == expected, (
            f"Expected metadata-derived label '{expected}', got '{link['label']}'"
        )
        assert not _re.match(r'^Link\s+\d+$', link["label"]), (
            f"Fallback label '{link['label']}' should not be generic 'Link N' "
            f"when anchor_text metadata is available"
        )

    # Letters are now assigned by assign_letters(), not classify_links()
    from bedrock_classifier import assign_letters
    lettered = assign_letters(result)
    assert len(lettered) == n
    for link in lettered:
        assert "letter" in link, "Fallback links should have letter assignments after assign_letters()"


# ---------------------------------------------------------------------------
# Test 2.5 — Single-Column Order Preservation  (Requirement 3.5)
# ---------------------------------------------------------------------------

@given(
    n=st.integers(min_value=2, max_value=6),
    data=st.data(),
)
@settings(max_examples=10, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
def test_single_column_order_preservation(n, data):
    """
    **Validates: Requirements 3.5**

    In single-column HTML where source order matches visual order,
    classify_links() assigns letters sequentially A, B, C, ...
    This is existing behavior that must be preserved.
    """
    from bedrock_classifier import classify_links

    segments = data.draw(
        st.lists(_url_segment, min_size=n, max_size=n, unique=True),
        label="url_segments",
    )
    anchors = data.draw(
        st.lists(_descriptive_text, min_size=n, max_size=n, unique_by=lambda t: t.strip().lower()),
        label="anchors",
    )

    raw_links = [
        {
            "url": f"https://example.com/{seg}",
            "anchor_text": anc,
            "context": f"Context for {anc}",
        }
        for seg, anc in zip(segments, anchors)
    ]

    # Mock Bedrock to include all links with descriptive labels
    classifications = [
        {"label": f"Label for {anc}", "include": True}
        for anc in anchors
    ]
    mock_resp = _make_mock_bedrock_response(classifications)

    with patch("bedrock_classifier.bedrock") as mock_bedrock:
        mock_bedrock.invoke_model.return_value = mock_resp
        result = classify_links(raw_links)

    # All links should be included
    assert len(result) == n, (
        f"Expected {n} classified links, got {len(result)}"
    )

    # Letters are now assigned by assign_letters(), not classify_links()
    from bedrock_classifier import assign_letters
    lettered = assign_letters(result)
    assert len(lettered) == n

    # Letters should be sequential A, B, C, ...
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i, link in enumerate(lettered):
        expected_letter = letters[i]
        assert link["letter"] == expected_letter, (
            f"Expected letter '{expected_letter}' at position {i}, "
            f"got '{link['letter']}'"
        )
