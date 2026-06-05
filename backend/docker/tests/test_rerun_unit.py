"""
Unit tests for HTML and images persistence in the annotation pipeline.

Feature: rerun-annotation
Validates: Requirements 1.1, 1.3, 1.4, 6.1
"""

import sys
import os
import json
from unittest.mock import patch, MagicMock, call

import pytest

# Add parent directory to path so we can import the modules under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required environment variables before importing handler
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("SES_FROM_EMAIL", "test@example.com")

# Stub out heavy third-party modules that handler.py imports at module level
for mod_name in [
    "reportlab", "reportlab.lib", "reportlab.lib.units", "reportlab.lib.pagesizes",
    "reportlab.lib.colors", "reportlab.lib.styles", "reportlab.lib.enums",
    "reportlab.platypus", "reportlab.pdfgen", "reportlab.pdfgen.canvas",
    "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _mock_pipeline_deps():
    """Return a dict of patch context managers for all pipeline dependencies."""
    return {
        "extract_links": patch("handler.extract_links", return_value=[]),
        "classify_links": patch("handler.classify_links", return_value=[]),
        "assign_letters": patch("handler.assign_letters", return_value=[]),
        "review_email": patch("handler.review_email", return_value={
            "overall_score": 85,
            "overall_summary": "Good",
            "issue_counts": {"critical": 0, "warning": 0, "info": 0},
            "issues": [],
        }),
        "capture_screenshots": patch("handler.capture_screenshots", return_value=(
            b"desktop_png", b"mobile_png", [], [],
        )),
        "annotate_screenshot": patch("handler.annotate_screenshot", return_value=(
            b"annotated_png", {"confidence": 100, "matched": 0, "total": 0},
        )),
        "build_pdf": patch("handler.build_pdf", return_value=b"fake_pdf_bytes"),
        "send_email": patch("handler._send_email"),
    }


def _run_pipeline_with_mocks(mock_s3, **pipeline_kwargs):
    """Run _run_pipeline with all pipeline deps mocked, using the given mock_s3."""
    from handler import _run_pipeline

    patches = _mock_pipeline_deps()
    with patch("handler.s3", mock_s3), \
         patch("handler._extract_images_zip", return_value="/tmp/fake_work_dir"), \
         patch("handler._rewrite_image_paths", side_effect=lambda html, _wd: html), \
         patch("handler._collect_images_b64", return_value={}), \
         patch("os.path.isdir", return_value=False), \
         patches["extract_links"], patches["classify_links"], \
         patches["assign_letters"], patches["review_email"], \
         patches["capture_screenshots"], patches["annotate_screenshot"], \
         patches["build_pdf"], patches["send_email"]:
        return _run_pipeline(**pipeline_kwargs)


def _make_default_s3_mock():
    """Create a standard mock S3 client that succeeds on all calls."""
    mock_s3 = MagicMock()
    mock_s3.put_object.return_value = {}
    mock_s3.copy_object.return_value = {}
    mock_s3.generate_presigned_url.return_value = "https://fake-url.com/pdf"
    mock_s3.delete_object.return_value = {}
    return mock_s3


# ---------------------------------------------------------------------------
# Test 1: HTML stored with correct S3 key and content type
# Validates: Requirement 1.1
# ---------------------------------------------------------------------------

def test_html_stored_with_correct_key_and_content_type():
    """
    WHEN the pipeline completes successfully,
    THEN it SHALL store the original HTML at html/{job_id}/original.html
    with ContentType='text/html'.
    """
    mock_s3 = _make_default_s3_mock()
    job_id = "abc12345"
    html = "<html><body>Hello World</body></html>"

    result = _run_pipeline_with_mocks(
        mock_s3,
        html_content=html,
        html_content_original=html,
        filename="campaign.html",
        subject_line="Spring Sale",
        preheader_text="Don't miss out",
        recipient_email="user@example.com",
        images_s3_key="",
        job_id=job_id,
        user_email="user@example.com",
        rerun_from=None,
    )

    assert json.loads(result["body"])["job_id"] == job_id

    # Find the HTML persistence call
    html_put_calls = [
        c for c in mock_s3.put_object.call_args_list
        if c.kwargs.get("Key") == f"html/{job_id}/original.html"
    ]
    assert len(html_put_calls) == 1, (
        f"Expected exactly 1 put_object for html/{job_id}/original.html, "
        f"got {len(html_put_calls)}"
    )
    assert html_put_calls[0].kwargs["ContentType"] == "text/html"
    assert html_put_calls[0].kwargs["Body"] == html
    assert html_put_calls[0].kwargs["Bucket"] == "test-bucket"


# ---------------------------------------------------------------------------
# Test 2: images_s3_key included in job record when provided
# Validates: Requirement 1.3
# ---------------------------------------------------------------------------

def test_images_s3_key_in_job_record():
    """
    WHEN the pipeline completes with an images_s3_key,
    THEN the job record stored in S3 SHALL include the images_s3_key value.
    """
    mock_s3 = _make_default_s3_mock()
    job_id = "img12345"
    images_key = "uploads/abc123/images.zip"

    result = _run_pipeline_with_mocks(
        mock_s3,
        html_content="<html><body>Test</body></html>",
        html_content_original="<html><body>Test</body></html>",
        filename="test.html",
        subject_line="Test",
        preheader_text="",
        recipient_email="user@example.com",
        images_s3_key=images_key,
        job_id=job_id,
        user_email="user@example.com",
        rerun_from=None,
    )

    # Find the job record put_object call (Key starts with "history/")
    history_calls = [
        c for c in mock_s3.put_object.call_args_list
        if c.kwargs.get("Key", "").startswith("history/")
    ]
    assert len(history_calls) == 1, (
        f"Expected 1 history put_object call, got {len(history_calls)}"
    )

    job_record = json.loads(history_calls[0].kwargs["Body"])
    assert job_record["images_s3_key"] == images_key, (
        f"Expected images_s3_key='{images_key}', got '{job_record.get('images_s3_key')}'"
    )


# ---------------------------------------------------------------------------
# Test 3: HTML persistence failure doesn't crash pipeline
# Validates: Requirement 1.4
# ---------------------------------------------------------------------------

def test_html_persistence_failure_continues_pipeline():
    """
    IF the S3 put for html/{job_id}/original.html fails,
    THEN the pipeline SHALL still return 200 with a valid response.
    """
    mock_s3 = _make_default_s3_mock()
    job_id = "fail1234"

    # Make put_object fail ONLY for the html/ key
    def selective_put_failure(**kwargs):
        key = kwargs.get("Key", "")
        if key.startswith("html/") and key.endswith("/original.html"):
            raise Exception("Simulated S3 failure for HTML persistence")
        return {}

    mock_s3.put_object.side_effect = selective_put_failure

    result = _run_pipeline_with_mocks(
        mock_s3,
        html_content="<html><body>Resilient</body></html>",
        html_content_original="<html><body>Resilient</body></html>",
        filename="resilient.html",
        subject_line="Test",
        preheader_text="",
        recipient_email="user@example.com",
        images_s3_key="",
        job_id=job_id,
        user_email="user@example.com",
        rerun_from=None,
    )

    assert result["statusCode"] == 200, (
        f"Expected 200, got {result['statusCode']}: {result['body']}"
    )
    body = json.loads(result["body"])
    assert body["job_id"] == job_id
    assert "pdf_url" in body


# ---------------------------------------------------------------------------
# Test 4: Images ZIP copied to persistent location
# Validates: Requirement 6.1
# ---------------------------------------------------------------------------

def test_images_zip_copied_to_persistent_location():
    """
    WHEN the pipeline completes with an images_s3_key,
    THEN it SHALL copy the images ZIP to html/{job_id}/images.zip.
    """
    mock_s3 = _make_default_s3_mock()
    job_id = "zip12345"
    images_key = "uploads/abc123/images.zip"

    result = _run_pipeline_with_mocks(
        mock_s3,
        html_content="<html><body>With images</body></html>",
        html_content_original="<html><body>With images</body></html>",
        filename="images_test.html",
        subject_line="Test",
        preheader_text="",
        recipient_email="user@example.com",
        images_s3_key=images_key,
        job_id=job_id,
        user_email="user@example.com",
        rerun_from=None,
    )

    # Verify copy_object was called with the right args
    copy_calls = [
        c for c in mock_s3.copy_object.call_args_list
        if c.kwargs.get("Key") == f"html/{job_id}/images.zip"
    ]
    assert len(copy_calls) == 1, (
        f"Expected 1 copy_object for html/{job_id}/images.zip, got {len(copy_calls)}"
    )
    copy_source = copy_calls[0].kwargs["CopySource"]
    assert copy_source["Key"] == images_key, (
        f"Expected CopySource Key='{images_key}', got '{copy_source.get('Key')}'"
    )
    assert copy_source["Bucket"] == "test-bucket"
