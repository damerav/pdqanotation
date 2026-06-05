"""
Bug condition exploration tests for generic "Link N" label bug.

These property-based tests verify that the FIXED code no longer produces
generic "Link N" labels when meaningful metadata is available. Each test
mocks Bedrock to simulate a specific failure scenario and asserts that
output labels are derived from link metadata instead of falling back to
generic patterns.

Validates: Property 1 — Bug Condition: Metadata-Derived Labels Replace Generic Fallbacks
"""

import sys
import os
import json
import re
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Add parent directory to path so we can import the modules under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bedrock_classifier import classify_links


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_generic_label(label: str) -> bool:
    """Return True if label matches the generic 'Link N' pattern."""
    return bool(re.match(r'^Link\s+\d+$', label))


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


# Strategy: non-empty anchor text (letters/digits/spaces, 3-40 chars)
_anchor_text = st.text(
    alphabet=st.characters(min_codepoint=65, max_codepoint=122,
                           whitelist_categories=("L", "N", "Zs")),
    min_size=3,
    max_size=40,
).filter(lambda t: t.strip() != "" and not _is_generic_label(t.strip()))

# Strategy: URL path segment
_url_segment = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=4,
    max_size=12,
)


# ---------------------------------------------------------------------------
# 5.1 — Partial Bedrock response: fewer classifications than input links
# ---------------------------------------------------------------------------

@given(
    num_links=st.integers(min_value=3, max_value=5),
    num_classifications=st.integers(min_value=1, max_value=2),
    data=st.data(),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_partial_bedrock_response_no_generic_labels(num_links, num_classifications, data):
    """
    **Validates: Requirements 2.1**

    Property 1: Bug Condition - Metadata-Derived Labels Replace Generic Fallbacks

    When Bedrock returns fewer classifications than input links, the trailing
    links (those beyond the classification count) must NOT receive generic
    "Link N" labels if they have non-empty anchor_text.
    """
    # Generate unique anchors and URL segments
    anchors = data.draw(
        st.lists(_anchor_text, min_size=num_links, max_size=num_links,
                 unique_by=lambda t: t.strip().lower()),
        label="anchors",
    )
    segments = data.draw(
        st.lists(_url_segment, min_size=num_links, max_size=num_links, unique=True),
        label="segments",
    )

    raw_links = [
        {
            "url": f"https://example.com/{seg}",
            "anchor_text": anc,
            "context": f"Some context around {anc} link in the email body",
        }
        for seg, anc in zip(segments, anchors)
    ]

    # Bedrock returns only num_classifications results (fewer than num_links)
    classifications = [
        {"label": f"Descriptive Label {i}", "include": True}
        for i in range(num_classifications)
    ]
    mock_resp = _make_mock_bedrock_response(classifications)

    with patch("bedrock_classifier.bedrock") as mock_bedrock:
        mock_bedrock.invoke_model.return_value = mock_resp
        result = classify_links(raw_links)

    # All links should be in the result (all have include: True or fallback)
    assert len(result) == num_links, (
        f"Expected {num_links} links, got {len(result)}"
    )

    # The trailing links (beyond classification count) must NOT have generic labels
    for i in range(num_classifications, num_links):
        label = result[i]["label"]
        assert not _is_generic_label(label), (
            f"Link at index {i} got generic label '{label}' instead of "
            f"metadata-derived label (anchor_text='{anchors[i].strip()}')"
        )


# ---------------------------------------------------------------------------
# 5.2 — Bedrock failure: exception raised, all links get fallback
# ---------------------------------------------------------------------------

@given(
    num_links=st.integers(min_value=2, max_value=5),
    data=st.data(),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_bedrock_exception_no_generic_labels(num_links, data):
    """
    **Validates: Requirements 2.2**

    Property 1: Bug Condition - Metadata-Derived Labels Replace Generic Fallbacks

    When Bedrock raises an exception, ALL output labels must be derived from
    link metadata (anchor_text, URL, img_alt) — none should match the
    generic "Link N" pattern when metadata is available.
    """
    anchors = data.draw(
        st.lists(_anchor_text, min_size=num_links, max_size=num_links,
                 unique_by=lambda t: t.strip().lower()),
        label="anchors",
    )
    segments = data.draw(
        st.lists(_url_segment, min_size=num_links, max_size=num_links, unique=True),
        label="segments",
    )

    raw_links = [
        {
            "url": f"https://example.com/{seg}",
            "anchor_text": anc,
            "context": f"Context for {anc}",
        }
        for seg, anc in zip(segments, anchors)
    ]

    with patch("bedrock_classifier.bedrock") as mock_bedrock:
        mock_bedrock.invoke_model.side_effect = Exception("Service unavailable")
        result = classify_links(raw_links)

    assert len(result) == num_links, (
        f"Expected {num_links} links in fallback, got {len(result)}"
    )

    for i, link in enumerate(result):
        assert not _is_generic_label(link["label"]), (
            f"Link at index {i} got generic label '{link['label']}' "
            f"instead of metadata-derived label (anchor_text='{anchors[i].strip()}')"
        )


# ---------------------------------------------------------------------------
# 5.3 — Bedrock returns "Link N" labels for links with anchor_text
# ---------------------------------------------------------------------------

@given(
    num_links=st.integers(min_value=2, max_value=5),
    data=st.data(),
)
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_generic_bedrock_labels_replaced_by_anchor_text(num_links, data):
    """
    **Validates: Requirements 2.4**

    Property 1: Bug Condition - Metadata-Derived Labels Replace Generic Fallbacks

    When Bedrock returns "Link N" labels for links that have non-empty
    anchor_text, the post-processing step must replace those generic labels
    with the link's anchor_text.
    """
    anchors = data.draw(
        st.lists(_anchor_text, min_size=num_links, max_size=num_links,
                 unique_by=lambda t: t.strip().lower()),
        label="anchors",
    )
    segments = data.draw(
        st.lists(_url_segment, min_size=num_links, max_size=num_links, unique=True),
        label="segments",
    )

    raw_links = [
        {
            "url": f"https://example.com/{seg}",
            "anchor_text": anc,
            "context": f"Context for {anc}",
        }
        for seg, anc in zip(segments, anchors)
    ]

    # Bedrock returns generic "Link N" labels for every link
    classifications = [
        {"label": f"Link {i + 1}", "include": True}
        for i in range(num_links)
    ]
    mock_resp = _make_mock_bedrock_response(classifications)

    with patch("bedrock_classifier.bedrock") as mock_bedrock:
        mock_bedrock.invoke_model.return_value = mock_resp
        result = classify_links(raw_links)

    assert len(result) == num_links, (
        f"Expected {num_links} links, got {len(result)}"
    )

    for i, link in enumerate(result):
        assert not _is_generic_label(link["label"]), (
            f"Link at index {i} still has generic label '{link['label']}' "
            f"— expected anchor_text-derived label '{anchors[i].strip()[:60]}'"
        )
        # The label should be the anchor_text (truncated to 60 chars)
        expected = anchors[i].strip()[:60]
        assert link["label"] == expected, (
            f"Link at index {i} label '{link['label']}' does not match "
            f"expected anchor_text '{expected}'"
        )
