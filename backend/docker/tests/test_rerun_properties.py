"""
Property-based tests for the re-run annotation feature.

Feature: rerun-annotation
Validates correctness properties defined in the design document.
"""

import sys
import os
import json
import types
from unittest.mock import patch, MagicMock

import pytest
from botocore.exceptions import ClientError
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# Add parent directory to path so we can import the modules under test
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set required environment variables before importing handler
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("SES_FROM_EMAIL", "test@example.com")

# Stub out heavy third-party modules that handler.py imports at module level
# so we don't need reportlab, PIL, playwright, etc. installed in the test env.
for mod_name in [
    "reportlab", "reportlab.lib", "reportlab.lib.units", "reportlab.lib.pagesizes",
    "reportlab.lib.colors", "reportlab.lib.styles", "reportlab.lib.enums",
    "reportlab.platypus", "reportlab.pdfgen", "reportlab.pdfgen.canvas",
    "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageFont",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = MagicMock()


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate HTML strings that pass the handler's content-type validation.
# The handler requires content to start with <html, <!doctype, <head, or <body.
_html_body = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z", "S"),
        min_codepoint=32,
        max_codepoint=1000,
    ),
    min_size=0,
    max_size=500,
)

_valid_html = _html_body.map(
    lambda body: f"<html><body>{body}</body></html>"
)


# ---------------------------------------------------------------------------
# Property 1: HTML content preservation (round-trip)
# ---------------------------------------------------------------------------

@given(html_content=_valid_html)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_html_content_preservation(html_content):
    """
    Feature: rerun-annotation, Property 1: HTML content preservation

    **Validates: Requirements 1.2**

    For any valid HTML string submitted as html_content, the content stored
    in S3 at html/{job_id}/original.html SHALL be byte-identical to the
    original input, before any image path rewriting is applied.
    """
    from handler import _run_pipeline

    mock_s3 = MagicMock()
    mock_s3.put_object.return_value = {}
    mock_s3.generate_presigned_url.return_value = "https://fake-url.com/pdf"

    # Mock all pipeline dependencies so no external calls are made
    with patch("handler.s3", mock_s3), \
         patch("handler.extract_links", return_value=[]), \
         patch("handler.classify_links", return_value=[]), \
         patch("handler.assign_letters", return_value=[]), \
         patch("handler.review_email", return_value={
             "overall_score": 85,
             "overall_summary": "Good",
             "issue_counts": {"critical": 0, "warning": 0, "info": 0},
             "issues": [],
         }), \
         patch("handler.capture_screenshots", return_value=(
             b"desktop_png", b"mobile_png", [], [],
         )), \
         patch("handler.annotate_screenshot", return_value=(
             b"annotated_png", {"confidence": 100, "matched": 0, "total": 0},
         )), \
         patch("handler.build_pdf", return_value=b"fake_pdf_bytes"), \
         patch("handler._send_email"):

        result = _run_pipeline(
            html_content=html_content,
            html_content_original=html_content,
            filename="test.html",
            subject_line="Test Subject",
            preheader_text="Test Preheader",
            recipient_email="user@example.com",
            images_s3_key="",
            job_id="test1234",
            user_email="user@example.com",
            rerun_from=None,
        )

    # Find the put_object call that stores the original HTML
    html_put_calls = [
        c for c in mock_s3.put_object.call_args_list
        if c.kwargs.get("Key", "").startswith("html/")
        and c.kwargs.get("Key", "").endswith("/original.html")
    ]

    assert len(html_put_calls) == 1, (
        f"Expected exactly 1 S3 put_object call for html/*/original.html, "
        f"got {len(html_put_calls)}"
    )

    stored_body = html_put_calls[0].kwargs["Body"]
    assert stored_body == html_content, (
        f"Stored HTML is not byte-identical to original input.\n"
        f"Original length: {len(html_content)}, Stored length: {len(stored_body)}"
    )


# ---------------------------------------------------------------------------
# Strategies for Property 2
# ---------------------------------------------------------------------------

# Non-empty strings for "provided" field values
_nonempty_str = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        min_codepoint=32,
        max_codepoint=500,
    ),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip() != "")

# Field value: either a non-empty string (provided) or empty string (omitted)
_field_value = st.one_of(st.just(""), _nonempty_str)

# Original job record field values (always non-empty so we can verify fallback)
_original_field_value = _nonempty_str


# ---------------------------------------------------------------------------
# Property 2: Re-run field defaulting
# ---------------------------------------------------------------------------

@given(
    provided_filename=_field_value,
    provided_subject=_field_value,
    provided_preheader=_field_value,
    original_filename=_original_field_value,
    original_subject=_original_field_value,
    original_preheader=_original_field_value,
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_rerun_field_defaulting(
    provided_filename,
    provided_subject,
    provided_preheader,
    original_filename,
    original_subject,
    original_preheader,
):
    """
    Feature: rerun-annotation, Property 2: Re-run field defaulting

    **Validates: Requirements 2.2**

    For any re-run request and original job record, if a field (filename,
    subject_line, preheader_text) is provided in the re-run request body
    (non-empty string), the pipeline SHALL use the provided value; otherwise
    it SHALL use the corresponding value from the original job record.
    """
    from handler import _handle_rerun

    rerun_job_id = "orig1234"
    user_email = "testuser@example.com"

    # Build the event with JWT claims
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "email": user_email,
                    "cognito:groups": "",
                }
            }
        }
    }

    # Build the request body with provided field values
    body = {
        "rerun_job_id": rerun_job_id,
        "filename": provided_filename,
        "subject_line": provided_subject,
        "preheader_text": provided_preheader,
    }

    # Build the original job record that S3 would return
    original_record = {
        "job_id": rerun_job_id,
        "filename": original_filename,
        "subject_line": original_subject,
        "preheader_text": original_preheader,
        "recipient_email": "original@example.com",
    }

    html_content = "<html><body>Test</body></html>"

    # Mock S3 to handle all the calls _handle_rerun makes
    mock_s3 = MagicMock()

    # head_object for ownership check — succeed (user owns the job)
    mock_s3.head_object.return_value = {}

    # get_object calls: first for HTML, second for job record, then images check
    def mock_get_object(Bucket, Key):
        mock_resp = MagicMock()
        if Key == f"html/{rerun_job_id}/original.html":
            mock_resp["Body"].read.return_value = html_content.encode("utf-8")
        elif Key == f"history/{user_email}/{rerun_job_id}.json":
            mock_resp["Body"].read.return_value = json.dumps(original_record).encode("utf-8")
        else:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
                "GetObject",
            )
        return mock_resp

    mock_s3.get_object.side_effect = mock_get_object

    # head_object for images.zip check — raise 404 (no images)
    original_head = mock_s3.head_object
    call_count = {"n": 0}

    def mock_head_object(Bucket, Key):
        call_count["n"] += 1
        if Key == f"html/{rerun_job_id}/images.zip":
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not found"}},
                "HeadObject",
            )
        # Ownership check — succeed
        return {}

    mock_s3.head_object.side_effect = mock_head_object

    # Mock _run_pipeline to capture the arguments it receives
    mock_pipeline = MagicMock(return_value={
        "statusCode": 200,
        "headers": {},
        "body": json.dumps({"job_id": "new12345"}),
    })

    with patch("handler.s3", mock_s3), \
         patch("handler._run_pipeline", mock_pipeline):
        result = _handle_rerun(event, body, rerun_job_id)

    # Verify _run_pipeline was called
    assert mock_pipeline.called, "_run_pipeline was not called"

    # Extract the keyword arguments passed to _run_pipeline
    call_kwargs = mock_pipeline.call_args.kwargs

    # Compute expected values: provided if non-empty, else original
    expected_filename = provided_filename if provided_filename else original_filename
    expected_subject = provided_subject if provided_subject else original_subject
    expected_preheader = provided_preheader if provided_preheader else original_preheader

    assert call_kwargs["filename"] == expected_filename, (
        f"filename mismatch: provided={provided_filename!r}, "
        f"original={original_filename!r}, "
        f"expected={expected_filename!r}, got={call_kwargs['filename']!r}"
    )
    assert call_kwargs["subject_line"] == expected_subject, (
        f"subject_line mismatch: provided={provided_subject!r}, "
        f"original={original_subject!r}, "
        f"expected={expected_subject!r}, got={call_kwargs['subject_line']!r}"
    )
    assert call_kwargs["preheader_text"] == expected_preheader, (
        f"preheader_text mismatch: provided={provided_preheader!r}, "
        f"original={original_preheader!r}, "
        f"expected={expected_preheader!r}, got={call_kwargs['preheader_text']!r}"
    )


# ---------------------------------------------------------------------------
# Strategies for Property 4
# ---------------------------------------------------------------------------

# Email-like strings for user identity
_email_str = st.from_regex(
    r"[a-z][a-z0-9]{1,10}@[a-z]{2,8}\.[a-z]{2,4}", fullmatch=True
)

# Short alphanumeric job IDs (matching the 8-char hex pattern used in production)
_job_id_str = st.from_regex(r"[a-f0-9]{8}", fullmatch=True)


# ---------------------------------------------------------------------------
# Property 4: Authorization — ownership enforcement
# ---------------------------------------------------------------------------

@given(
    user_email=_email_str,
    rerun_job_id=_job_id_str,
    is_admin=st.booleans(),
    owns_job=st.booleans(),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_authorization_ownership_enforcement(
    user_email,
    rerun_job_id,
    is_admin,
    owns_job,
):
    """
    Feature: rerun-annotation, Property 4: Authorization — ownership enforcement

    **Validates: Requirements 2.6, 2.7**

    For any user email, job_id, and admin status: if the user is not an admin
    and history/{user_email}/{job_id}.json does not exist in S3, the re-run
    request SHALL be rejected with HTTP 403. If the user is an admin, the
    re-run request SHALL proceed regardless of ownership.
    """
    from handler import _handle_rerun

    # Build the event with JWT claims
    groups = "admin" if is_admin else ""
    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "email": user_email,
                    "cognito:groups": groups,
                }
            }
        }
    }

    body = {"rerun_job_id": rerun_job_id}

    html_content = "<html><body>Test</body></html>"
    original_record = {
        "job_id": rerun_job_id,
        "filename": "test.html",
        "subject_line": "Test",
        "preheader_text": "",
        "recipient_email": "original@example.com",
    }

    mock_s3 = MagicMock()

    # Configure head_object to reflect ownership and images check
    def mock_head_object(Bucket, Key):
        # Ownership check: history/{user_email}/{rerun_job_id}.json
        if Key == f"history/{user_email}/{rerun_job_id}.json":
            if owns_job:
                return {}
            else:
                raise ClientError(
                    {"Error": {"Code": "404", "Message": "Not found"}},
                    "HeadObject",
                )
        # Images ZIP check: html/{rerun_job_id}/images.zip — always 404 (no images)
        if Key == f"html/{rerun_job_id}/images.zip":
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not found"}},
                "HeadObject",
            )
        return {}

    mock_s3.head_object.side_effect = mock_head_object

    # Configure get_object for HTML and job record retrieval
    def mock_get_object(Bucket, Key):
        mock_resp = MagicMock()
        if Key == f"html/{rerun_job_id}/original.html":
            mock_resp["Body"].read.return_value = html_content.encode("utf-8")
        elif Key == f"history/{user_email}/{rerun_job_id}.json":
            mock_resp["Body"].read.return_value = json.dumps(original_record).encode("utf-8")
        else:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
                "GetObject",
            )
        return mock_resp

    mock_s3.get_object.side_effect = mock_get_object

    # Mock _run_pipeline so we don't execute the full pipeline
    mock_pipeline = MagicMock(return_value={
        "statusCode": 200,
        "headers": {},
        "body": json.dumps({"job_id": "new12345"}),
    })

    with patch("handler.s3", mock_s3), \
         patch("handler._run_pipeline", mock_pipeline):
        result = _handle_rerun(event, body, rerun_job_id)

    status_code = result["statusCode"]
    response_body = json.loads(result["body"])

    if not is_admin and not owns_job:
        # Non-admin, non-owner → MUST get 403 FORBIDDEN
        assert status_code == 403, (
            f"Expected 403 for non-admin non-owner, got {status_code}. "
            f"email={user_email!r}, job_id={rerun_job_id!r}, "
            f"is_admin={is_admin}, owns_job={owns_job}"
        )
        assert response_body["error"] == "FORBIDDEN", (
            f"Expected error='FORBIDDEN', got {response_body.get('error')!r}"
        )
        # Pipeline should NOT have been called
        assert not mock_pipeline.called, (
            "Pipeline should not run when user is non-admin and does not own the job"
        )
    else:
        # Admin OR owner → request should proceed (pipeline called, 200 returned)
        assert status_code == 200, (
            f"Expected 200 for authorized user, got {status_code}. "
            f"email={user_email!r}, job_id={rerun_job_id!r}, "
            f"is_admin={is_admin}, owns_job={owns_job}, "
            f"body={response_body}"
        )
        assert mock_pipeline.called, (
            f"Pipeline should run when user is authorized. "
            f"is_admin={is_admin}, owns_job={owns_job}"
        )


# ---------------------------------------------------------------------------
# Property 5: Re-run traceability
# ---------------------------------------------------------------------------

@given(rerun_job_id=_job_id_str)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_rerun_traceability(rerun_job_id):
    """
    Feature: rerun-annotation, Property 5: Re-run traceability

    **Validates: Requirements 3.2**

    For any re-run job, the resulting job record's `rerun_from` field SHALL
    equal the `rerun_job_id` from the request.
    """
    from handler import _handle_rerun

    user_email = "testuser@example.com"

    event = {
        "requestContext": {
            "authorizer": {
                "claims": {
                    "email": user_email,
                    "cognito:groups": "",
                }
            }
        }
    }

    body = {"rerun_job_id": rerun_job_id}

    html_content = "<html><body>Test</body></html>"
    original_record = {
        "job_id": rerun_job_id,
        "filename": "test.html",
        "subject_line": "Test Subject",
        "preheader_text": "Test Preheader",
        "recipient_email": "original@example.com",
    }

    mock_s3 = MagicMock()

    # Ownership check — succeed (user owns the job)
    def mock_head_object(Bucket, Key):
        if Key == f"html/{rerun_job_id}/images.zip":
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not found"}},
                "HeadObject",
            )
        return {}

    mock_s3.head_object.side_effect = mock_head_object

    # get_object for HTML and job record
    def mock_get_object(Bucket, Key):
        mock_resp = MagicMock()
        if Key == f"html/{rerun_job_id}/original.html":
            mock_resp["Body"].read.return_value = html_content.encode("utf-8")
        elif Key == f"history/{user_email}/{rerun_job_id}.json":
            mock_resp["Body"].read.return_value = json.dumps(original_record).encode("utf-8")
        else:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
                "GetObject",
            )
        return mock_resp

    mock_s3.get_object.side_effect = mock_get_object
    mock_s3.put_object.return_value = {}
    mock_s3.generate_presigned_url.return_value = "https://fake-url.com/pdf"
    mock_s3.delete_object.return_value = {}

    # Mock all pipeline dependencies so no external calls are made
    with patch("handler.s3", mock_s3), \
         patch("handler.extract_links", return_value=[]), \
         patch("handler.classify_links", return_value=[]), \
         patch("handler.assign_letters", return_value=[]), \
         patch("handler.review_email", return_value={
             "overall_score": 85,
             "overall_summary": "Good",
             "issue_counts": {"critical": 0, "warning": 0, "info": 0},
             "issues": [],
         }), \
         patch("handler.capture_screenshots", return_value=(
             b"desktop_png", b"mobile_png", [], [],
         )), \
         patch("handler.annotate_screenshot", return_value=(
             b"annotated_png", {"confidence": 100, "matched": 0, "total": 0},
         )), \
         patch("handler.build_pdf", return_value=b"fake_pdf_bytes"), \
         patch("handler._send_email"):

        result = _handle_rerun(event, body, rerun_job_id)

    # Verify the request succeeded
    assert result["statusCode"] == 200, (
        f"Expected 200, got {result['statusCode']}. Body: {result['body']}"
    )

    # Find the put_object call that stores the job record at history/{user_email}/{new_job_id}.json
    job_record_calls = [
        c for c in mock_s3.put_object.call_args_list
        if c.kwargs.get("Key", "").startswith(f"history/{user_email}/")
        and c.kwargs.get("Key", "").endswith(".json")
    ]

    assert len(job_record_calls) == 1, (
        f"Expected exactly 1 job record put_object call, got {len(job_record_calls)}"
    )

    stored_record = json.loads(job_record_calls[0].kwargs["Body"])

    assert stored_record["rerun_from"] == rerun_job_id, (
        f"Expected rerun_from={rerun_job_id!r}, "
        f"got {stored_record.get('rerun_from')!r}"
    )
