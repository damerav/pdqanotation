"""
Preservation property-based tests for the generic-link-labels bugfix.

These tests verify that the fix does NOT alter behavior for non-buggy inputs:
- Meaningful Bedrock labels are passed through unchanged
- The include/exclude filtering continues to work correctly

Validates: Property 2 — Preservation: Meaningful Bedrock Labels Unchanged
"""

import sys
import os
import json
import re
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, HealthCheck, assume
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


# Strategy: meaningful label that does NOT match "Link N" pattern
_meaningful_label = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs"),
                           min_codepoint=65, max_codepoint=122),
    min_size=5,
    max_size=40,
).filter(lambda t: t.strip() != "" and not _is_generic_label(t.strip()))

# Strategy: non-empty anchor text
_anchor_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs"),
                           min_codepoint=65, max_codepoint=122),
    min_size=3,
    max_size=30,
).filter(lambda t: t.strip() != "")

# Strategy: URL path segment
_url_segment = st.text(
    alphabet=st.characters(min_codepoint=97, max_codepoint=122),
    min_size=4,
    max_size=12,
)


# ---------------------------------------------------------------------------
# 7.1 — Meaningful label preservation
# ---------------------------------------------------------------------------

@given(
    num_links=st.integers(min_value=2, max_value=5),
    data=st.data(),
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_meaningful_labels_preserved_from_bedrock(num_links, data):
    """
    **Validates: Requirements 3.1, 3.3**

    Property 2: Preservation — Meaningful Bedrock Labels Unchanged

    When Bedrock returns meaningful (non-"Link N") labels with include:true
    for ALL links, the output labels must be identical to Bedrock's response.
    The fix must not modify labels that are already good.
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
    labels = data.draw(
        st.lists(_meaningful_label, min_size=num_links, max_size=num_links),
        label="labels",
    )

    # Ensure none of the generated labels are generic
    for lbl in labels:
        assume(not _is_generic_label(lbl.strip()))

    raw_links = [
        {
            "url": f"https://example.com/{seg}",
            "anchor_text": anc,
            "context": f"Some context around {anc} in the email body",
        }
        for seg, anc in zip(segments, anchors)
    ]

    # Bedrock returns meaningful labels with include:true for all links
    classifications = [
        {"label": lbl, "include": True}
        for lbl in labels
    ]
    mock_resp = _make_mock_bedrock_response(classifications)

    with patch("bedrock_classifier.bedrock") as mock_bedrock:
        mock_bedrock.invoke_model.return_value = mock_resp
        result = classify_links(raw_links)

    # All links should appear in output
    assert len(result) == num_links, (
        f"Expected {num_links} links, got {len(result)}"
    )

    # Each output label must exactly match the Bedrock-provided label
    for i, link in enumerate(result):
        assert link["label"] == labels[i], (
            f"Link at index {i}: expected label '{labels[i]}' from Bedrock, "
            f"got '{link['label']}'"
        )


# ---------------------------------------------------------------------------
# 7.2 — Include/exclude preservation
# ---------------------------------------------------------------------------

@given(
    num_links=st.integers(min_value=3, max_value=6),
    data=st.data(),
)
@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_include_exclude_preserved_from_bedrock(num_links, data):
    """
    **Validates: Requirements 3.1, 3.3**

    Property 2: Preservation — Meaningful Bedrock Labels Unchanged

    When Bedrock returns include:false for some links, those links must be
    excluded from the output. Links with include:true must appear with their
    correct labels. The count of output links must equal the count of
    include:true links.
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
    labels = data.draw(
        st.lists(_meaningful_label, min_size=num_links, max_size=num_links),
        label="labels",
    )
    include_flags = data.draw(
        st.lists(st.booleans(), min_size=num_links, max_size=num_links),
        label="include_flags",
    )

    # Ensure at least one included and one excluded link for a meaningful test
    assume(any(include_flags) and not all(include_flags))

    # Ensure none of the generated labels are generic
    for lbl in labels:
        assume(not _is_generic_label(lbl.strip()))

    raw_links = [
        {
            "url": f"https://example.com/{seg}",
            "anchor_text": anc,
            "context": f"Some context around {anc} in the email body",
        }
        for seg, anc in zip(segments, anchors)
    ]

    # Bedrock returns meaningful labels with mixed include flags
    classifications = [
        {"label": lbl, "include": inc}
        for lbl, inc in zip(labels, include_flags)
    ]
    mock_resp = _make_mock_bedrock_response(classifications)

    with patch("bedrock_classifier.bedrock") as mock_bedrock:
        mock_bedrock.invoke_model.return_value = mock_resp
        result = classify_links(raw_links)

    # Count expected included links
    expected_included = [i for i, inc in enumerate(include_flags) if inc]
    expected_excluded = [i for i, inc in enumerate(include_flags) if not inc]

    # Output count must match include:true count
    assert len(result) == len(expected_included), (
        f"Expected {len(expected_included)} included links, got {len(result)}. "
        f"Include flags: {include_flags}"
    )

    # Included links must have correct labels
    result_idx = 0
    for i in expected_included:
        assert result[result_idx]["label"] == labels[i], (
            f"Included link at original index {i}: expected label '{labels[i]}', "
            f"got '{result[result_idx]['label']}'"
        )
        assert result[result_idx]["url"] == raw_links[i]["url"], (
            f"Included link at original index {i}: URL mismatch"
        )
        result_idx += 1

    # Excluded links must NOT appear in output (check by URL)
    result_urls = {link["url"] for link in result}
    for i in expected_excluded:
        excluded_url = raw_links[i]["url"]
        assert excluded_url not in result_urls, (
            f"Link at index {i} with include:false (URL={excluded_url}) "
            f"should NOT be in output but was found"
        )
