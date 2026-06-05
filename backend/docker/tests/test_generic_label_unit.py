"""
Unit tests for the generic-link-labels bugfix.

6.1 — derive_label_from_metadata: anchor_text priority, img_alt fallback,
      URL path extraction, domain fallback, and last-resort "Link N"
6.2 — _is_generic_label: matches/non-matches
6.3 — context truncation is 500 characters in the Bedrock payload
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock, ANY

import pytest

# Add parent directory so we can import the module under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bedrock_classifier import derive_label_from_metadata, _is_generic_label, classify_links


# ---------------------------------------------------------------------------
# 6.1 — derive_label_from_metadata
# ---------------------------------------------------------------------------

class TestDeriveLabelFromMetadata:
    """Unit tests for derive_label_from_metadata priority chain."""

    def test_anchor_text_present_returns_anchor(self):
        """When anchor_text is present, it is returned (stripped)."""
        link = {"url": "https://example.com", "anchor_text": "  Privacy Policy  ", "context": ""}
        assert derive_label_from_metadata(link, 0) == "Privacy Policy"

    def test_anchor_text_truncated_at_60_chars(self):
        """anchor_text longer than 60 chars is truncated."""
        long_text = "A" * 80
        link = {"url": "https://example.com", "anchor_text": long_text, "context": ""}
        result = derive_label_from_metadata(link, 0)
        assert len(result) == 60
        assert result == "A" * 60

    def test_empty_anchor_text_img_alt_fallback(self):
        """When anchor_text is empty but img_alt is present, returns img_alt."""
        link = {"url": "https://example.com", "anchor_text": "", "img_alt": "Company Logo", "context": ""}
        assert derive_label_from_metadata(link, 0) == "Company Logo"

    def test_whitespace_anchor_text_img_alt_fallback(self):
        """When anchor_text is whitespace-only, falls through to img_alt."""
        link = {"url": "https://example.com", "anchor_text": "   ", "img_alt": "Banner Image", "context": ""}
        assert derive_label_from_metadata(link, 0) == "Banner Image"

    def test_url_path_extraction(self):
        """When anchor_text and img_alt are empty, derives label from URL path segment."""
        link = {"url": "https://example.com/prescribing-information", "anchor_text": "", "context": ""}
        assert derive_label_from_metadata(link, 0) == "Prescribing Information"

    def test_url_path_underscores_replaced(self):
        """Underscores in URL path segments are replaced with spaces and title-cased."""
        link = {"url": "https://example.com/privacy_policy", "anchor_text": "", "context": ""}
        assert derive_label_from_metadata(link, 0) == "Privacy Policy"

    def test_url_domain_fallback(self):
        """When URL has no meaningful path, returns the domain."""
        link = {"url": "https://safety.example.com/", "anchor_text": "", "context": ""}
        assert derive_label_from_metadata(link, 0) == "safety.example.com"

    def test_url_domain_fallback_no_path(self):
        """When URL has no path at all, returns the domain."""
        link = {"url": "https://example.com", "anchor_text": "", "context": ""}
        assert derive_label_from_metadata(link, 0) == "example.com"

    def test_last_resort_link_n(self):
        """When no metadata is available, returns 'Link {index+1}'."""
        link = {"url": "", "anchor_text": "", "context": ""}
        assert derive_label_from_metadata(link, 0) == "Link 1"
        assert derive_label_from_metadata(link, 4) == "Link 5"

    def test_no_metadata_at_all(self):
        """When the link dict has no useful keys, returns 'Link {index+1}'."""
        link = {}
        assert derive_label_from_metadata(link, 2) == "Link 3"


# ---------------------------------------------------------------------------
# 6.2 — _is_generic_label
# ---------------------------------------------------------------------------

class TestIsGenericLabel:
    """Unit tests for _is_generic_label regex matching."""

    @pytest.mark.parametrize("label", ["Link 1", "Link 10", "Link 123"])
    def test_true_cases(self, label):
        """Generic 'Link N' patterns should return True."""
        assert _is_generic_label(label) is True

    @pytest.mark.parametrize("label", [
        "Link to Privacy Policy",
        "Privacy Link",
        "",
        "Header Logo",
        "Link",
    ])
    def test_false_cases(self, label):
        """Non-generic labels should return False."""
        assert _is_generic_label(label) is False


# ---------------------------------------------------------------------------
# 6.3 — context truncation is 500 characters in the Bedrock payload
# ---------------------------------------------------------------------------

class TestContextTruncation:
    """Verify that context sent to Bedrock is truncated to 500 characters."""

    def test_context_truncated_to_500_chars(self):
        """When a link has context longer than 500 chars, the Bedrock payload
        should contain exactly 500 characters for that link's context field."""
        long_context = "x" * 800
        raw_links = [
            {"url": "https://example.com/page", "anchor_text": "Click here", "context": long_context}
        ]

        # Build a mock Bedrock response
        body_content = json.dumps({
            "output": {
                "message": {
                    "content": [{"text": json.dumps({"links": [{"label": "Click Here CTA", "include": True}]})}]
                }
            }
        }).encode()
        mock_resp = MagicMock()
        mock_resp.__getitem__ = lambda self, key: {
            "body": MagicMock(read=MagicMock(return_value=body_content))
        }[key]

        with patch("bedrock_classifier.bedrock") as mock_bedrock:
            mock_bedrock.invoke_model.return_value = mock_resp
            classify_links(raw_links)

            # Extract the body sent to invoke_model
            call_args = mock_bedrock.invoke_model.call_args
            sent_body = json.loads(call_args[1]["body"] if "body" in call_args[1] else call_args[0][1])
            user_text = sent_body["messages"][0]["content"][0]["text"]

            # Parse the JSON payload embedded in the user message
            # The format is: "Classify these links:\n[{...}]"
            payload_str = user_text.split("Classify these links:\n", 1)[1]
            payload = json.loads(payload_str)

            assert len(payload[0]["context"]) == 500


# ---------------------------------------------------------------------------
# Bug A regression — opaque ID / ad-redirect URLs must not yield junk labels
# (doubleclick "Link 9/10/11" recurrence). See campaign 26-026 report.
# ---------------------------------------------------------------------------

class TestOpaqueAndTrackingUrls:
    """Tracking/redirect URLs and opaque path IDs must never become labels."""

    # The exact URLs from the campaign 26-026 screenshots.
    DC_TRACKCLK = ("https://ad.doubleclick.net/ddm/trackclk/N848755.1119085PDQCOMMUNICATIONS/"
                   "B35118264.438708548;dc_trk_aid=631960545;dc_trk_cid=248565620;dc_lat=;"
                   "dc_rdid=;tag_for_child_directed_treatment=;tfua=;ltd=;dc_tdv=1")
    DC_CLK = "https://ad.doubleclick.net/ddm/clk/621883234;429065145;i;gdpr=${GDPR}"

    def test_doubleclick_no_metadata_does_not_emit_id(self):
        """A doubleclick redirect with no anchor/alt/context must not surface a raw ID."""
        link = {"url": self.DC_TRACKCLK, "anchor_text": "", "context": ""}
        label = derive_label_from_metadata(link, 8)
        assert "B35118264" not in label
        assert "438708548" not in label
        # With no other signal it is the honest last resort, not ID garbage.
        assert label == "Link 9"

    def test_doubleclick_clk_no_metadata_does_not_emit_id(self):
        link = {"url": self.DC_CLK, "anchor_text": "", "context": ""}
        label = derive_label_from_metadata(link, 13)
        assert "621883234" not in label
        assert label == "Link 14"

    def test_doubleclick_uses_context_when_available(self):
        """When a tracking link has surrounding context, the label comes from it."""
        link = {
            "url": self.DC_CLK,
            "anchor_text": "",
            "context": "Learn more about ongoing support for ACTEMRA. Click here to enroll.",
        }
        label = derive_label_from_metadata(link, 13)
        assert label == "Learn more about ongoing support for ACTEMRA"
        assert not _is_generic_label(label)

    def test_doubleclick_uses_img_alt_over_url(self):
        link = {"url": self.DC_CLK, "anchor_text": "",
                "img_alt": "PERJETA hero banner", "context": "some context"}
        assert derive_label_from_metadata(link, 0) == "PERJETA hero banner"

    def test_opaque_numeric_segment_falls_back_to_domain(self):
        """A non-tracking URL with an all-numeric path segment uses the domain."""
        link = {"url": "https://www.example.com/621883234", "anchor_text": "", "context": ""}
        assert derive_label_from_metadata(link, 0) == "example.com"

    def test_id_like_segment_rejected(self):
        """An ID-like segment (digits, no vowels) is rejected in favour of a real one."""
        link = {"url": "https://cdn.example.com/assets/B35118264/banner", "anchor_text": "", "context": ""}
        # "banner" is meaningful; the ID segment "B35118264" must be skipped.
        assert derive_label_from_metadata(link, 0) == "Banner"

    def test_meaningful_path_still_works_for_non_tracking(self):
        link = {"url": "https://www.drugpricinglaw.com/colorado-wac", "anchor_text": "", "context": ""}
        assert derive_label_from_metadata(link, 0) == "Colorado Wac"

    def test_nbsp_in_anchor_is_normalized(self):
        """Anchor text with a non-breaking space is normalised to a clean label."""
        link = {"url": self.DC_CLK, "anchor_text": "click\xa0here", "context": ""}
        assert derive_label_from_metadata(link, 0) == "click here"

    def test_context_only_label(self):
        """With only context available, a short clause is used."""
        link = {"url": "", "anchor_text": "",
                "context": "Please see the full Prescribing Information for BOXED WARNINGS."}
        label = derive_label_from_metadata(link, 0)
        assert label == "Please see the full Prescribing Information for BOXED"
        assert not _is_generic_label(label)
