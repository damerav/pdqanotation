import json
import os
import re
import shutil
import tempfile
import uuid
import zipfile
import boto3
from datetime import datetime

from html_parser import extract_links
from bedrock_classifier import classify_links
from bedrock_reviewer import review_email
from screenshot_generator import capture_screenshots
from image_annotator import annotate_screenshot
from pdf_builder import build_pdf

s3 = boto3.client("s3")
ses = boto3.client("ses", region_name=os.environ["AWS_REGION"])
BUCKET = os.environ["S3_BUCKET"]
SES_FROM = os.environ["SES_FROM_EMAIL"]

# Maximum allowed size for images ZIP (20 MB)
MAX_ZIP_SIZE = 20_000_000


def lambda_handler(event: dict, context) -> dict:
    """Route requests to the appropriate handler based on resource path."""
    resource = event.get("resource", "")
    method = event.get("httpMethod", "")

    if resource == "/upload-url" and method == "POST":
        return _handle_upload_url(event)
    elif resource == "/process" and method == "POST":
        return _handle_process(event)
    else:
        return _resp(404, {"error": "Not found"})


def _handle_upload_url(event: dict) -> dict:
    """Generate a pre-signed S3 PUT URL for uploading an images ZIP."""
    job_id = str(uuid.uuid4())[:8]
    s3_key = f"uploads/{job_id}/images.zip"

    presigned_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": BUCKET,
            "Key": s3_key,
            "ContentType": "application/zip",
        },
        ExpiresIn=900,  # 15 minutes to complete upload
    )

    return _resp(200, {
        "upload_url": presigned_url,
        "images_s3_key": s3_key,
        "job_id": job_id,
    })


def _handle_process(event: dict) -> dict:
    """Run the full annotation pipeline (parse → classify → review → screenshot → PDF → SES)."""
    body = json.loads(event.get("body", "{}"))

    html_content = body.get("html_content", "")
    filename = body.get("filename", "email.html")
    subject_line = body.get("subject_line", "")
    preheader_text = body.get("preheader_text", "")
    recipient_email = body.get("recipient_email", "")
    images_s3_key = body.get("images_s3_key", "")
    job_id = body.get("job_id", "") or str(uuid.uuid4())[:8]

    if not html_content or not recipient_email:
        return _resp(400, {"error": "html_content and recipient_email are required."})

    # SEC-11: File size limit (5 MB)
    if len(html_content) > 5_000_000:
        return _resp(400, {"error": "FILE_TOO_LARGE", "message": "HTML file exceeds 5 MB limit."})

    # SEC-12: Content type validation
    html_lower = html_content.strip().lower()
    if not any(html_lower.startswith(tag) for tag in ["<html", "<!doctype", "<head", "<body"]):
        return _resp(400, {"error": "INVALID_HTML", "message": "File does not appear to be valid HTML."})

    # SEC-3: Extract user email from JWT claims for history path
    user_email = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
        .get("email", recipient_email)
    )

    work_dir = None
    s3_prefix = f"pdfs/{job_id}"

    try:
        # If images ZIP was uploaded, extract and rewrite HTML image paths
        if images_s3_key:
            work_dir = _extract_images_zip(images_s3_key)
            html_content = _rewrite_image_paths(html_content, work_dir)

        # 1. Parse all links from HTML
        raw_links = extract_links(html_content)

        # 2. Bedrock Call #1 — Classify links (Claude 3 Haiku, fast + cheap)
        classified = classify_links(raw_links)

        # 3. Bedrock Call #2 — Full email quality review (Claude 3 Sonnet, thorough)
        review = review_email(html_content, raw_links, subject_line, preheader_text)

        # 4. Screenshots via Playwright headless Chromium
        desktop_bytes, mobile_bytes = capture_screenshots(html_content, work_dir=work_dir)

        # 5. Annotate screenshots with lettered callouts
        ann_desktop = annotate_screenshot(desktop_bytes, classified, "desktop")
        ann_mobile = annotate_screenshot(mobile_bytes, classified, "mobile")

        # 6. Build PDF — includes annotated screenshots, link table, and review report
        pdf_bytes = build_pdf(
            desktop_img=ann_desktop,
            mobile_img=ann_mobile,
            links=classified,
            review=review,
            subject=subject_line,
            preheader=preheader_text,
        )

        # 7. Save PDF to S3
        pdf_key = f"pdfs/{job_id}/{filename.replace('.html', '')}_annotated.pdf"
        s3.put_object(Bucket=BUCKET, Key=pdf_key, Body=pdf_bytes, ContentType="application/pdf")

        # 8. Generate pre-signed URL (7-day expiry)
        pdf_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": pdf_key},
            ExpiresIn=604800,
        )

        # 9. Send SES email with review summary + PDF link
        _send_email(recipient_email, filename, subject_line, pdf_url, review)

        # 10. Persist job record (SEC-3: use JWT email for history path)
        job_record = {
            "job_id": job_id,
            "filename": filename,
            "subject_line": subject_line,
            "recipient_email": recipient_email,
            "pdf_key": pdf_key,
            "pdf_url": pdf_url,
            "status": "done",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "review_score": review.get("overall_score"),
            "review_summary": review.get("overall_summary", ""),
            "issue_counts": review.get("issue_counts", {}),
        }
        s3.put_object(
            Bucket=BUCKET,
            Key=f"history/{user_email}/{job_id}.json",
            Body=json.dumps(job_record),
            ContentType="application/json",
        )

        return _resp(200, {
            "job_id": job_id,
            "pdf_url": pdf_url,
            "review_score": review.get("overall_score"),
            "issue_counts": review.get("issue_counts", {}),
            "review_summary": review.get("overall_summary", ""),
        })

    except Exception as e:
        print(f"[ERROR] job={job_id} error={e}")
        return _resp(500, {"error": str(e)})
    finally:
        # Clean up temp directory and uploaded ZIP from S3
        if work_dir and os.path.isdir(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
        if images_s3_key:
            try:
                s3.delete_object(Bucket=BUCKET, Key=images_s3_key)
            except Exception as cleanup_err:
                print(f"[WARN] Failed to delete uploaded ZIP: {cleanup_err}")


def _extract_images_zip(images_s3_key: str) -> str:
    """Download and extract images ZIP from S3 into a temp directory."""
    work_dir = tempfile.mkdtemp(prefix="email_images_")
    zip_path = os.path.join(work_dir, "images.zip")

    # Download ZIP from S3
    s3.download_file(BUCKET, images_s3_key, zip_path)

    # Validate ZIP size
    zip_size = os.path.getsize(zip_path)
    if zip_size > MAX_ZIP_SIZE:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise ValueError(f"Images ZIP exceeds {MAX_ZIP_SIZE // 1_000_000} MB limit.")

    # Extract ZIP contents (images only, skip dangerous paths and macOS metadata)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            # Skip macOS resource forks, hidden files, and path traversal
            basename = os.path.basename(member.filename)
            if ("__MACOSX" in member.filename or basename.startswith(".")
                    or "/.." in member.filename or member.filename.startswith("..")):
                continue
            if ".." in member.filename:
                continue
            lower_name = member.filename.lower()
            if not lower_name.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico")):
                continue
            zf.extract(member, work_dir)

    # Flatten nested duplicate folders (e.g. images/images/<files> → images/<files>)
    _flatten_nested_dirs(work_dir)

    # Remove the ZIP file after extraction
    os.unlink(zip_path)
    return work_dir


def _flatten_nested_dirs(work_dir: str) -> None:
    """Flatten ZIP artifacts where a folder contains only a single subfolder.

    Common patterns:
    - ``images.zip`` → ``images/images/<files>``  (same-name nesting)
    - ``index.zip``  → ``index/index/<files>``    (same-name nesting)
    - ``assets.zip``  → ``assets/dist/<files>``   (single-child nesting)
    This collapses the extra level so HTML relative paths resolve correctly.
    """
    for entry in os.listdir(work_dir):
        top = os.path.join(work_dir, entry)
        if not os.path.isdir(top):
            continue
        children = os.listdir(top)
        # If the only child is a single subdirectory, flatten it up
        if len(children) == 1:
            child_path = os.path.join(top, children[0])
            if os.path.isdir(child_path):
                for item in os.listdir(child_path):
                    src = os.path.join(child_path, item)
                    dst = os.path.join(top, item)
                    shutil.move(src, dst)
                os.rmdir(child_path)


def _rewrite_image_paths(html_content: str, work_dir: str) -> str:
    """Rewrite image src and CSS url() references to use absolute file:// paths."""
    # Build a map of filename -> absolute path for all extracted images.
    # ZIPs often nest like  index/index/<files>  or  images/images/<files>.
    # We register every possible path suffix so HTML refs like "images/header.jpg"
    # resolve even when the actual extracted path is "images/images/header.jpg".
    image_map: dict[str, str] = {}
    for root, _dirs, files in os.walk(work_dir):
        for fname in files:
            abs_path = os.path.join(root, fname)
            rel_path = os.path.relpath(abs_path, work_dir)
            # Normalise to forward slashes for consistent lookup
            rel_parts = rel_path.replace("\\", "/").lower().split("/")
            # Register the full relative path and every trailing sub-path.
            # e.g. "images/images/header.jpg" → also "images/header.jpg", "header.jpg"
            for i in range(len(rel_parts)):
                sub = "/".join(rel_parts[i:])
                # Only set if not already mapped (first match wins for duplicates)
                if sub not in image_map:
                    image_map[sub] = abs_path

    def _replace_src(match: re.Match) -> str:
        """Replace an image src attribute value with a file:// path."""
        prefix = match.group(1)  # 'src="' or "src='"
        original = match.group(2)
        suffix = match.group(3)  # closing quote

        # Skip data URIs, absolute URLs, and already-rewritten paths
        if original.startswith(("data:", "http://", "https://", "file://")):
            return match.group(0)

        # Normalise and look up in the suffix map
        lookup = original.replace("\\", "/").lower().lstrip("./")
        if lookup in image_map:
            return f'{prefix}file://{image_map[lookup]}{suffix}'
        return match.group(0)

    def _replace_css_url(match: re.Match) -> str:
        """Replace a CSS url() value with a file:// path."""
        prefix = match.group(1)  # 'url('
        quote = match.group(2) or ""
        original = match.group(3)
        suffix = match.group(4)  # closing paren

        if original.startswith(("data:", "http://", "https://", "file://")):
            return match.group(0)

        lookup = original.replace("\\", "/").lower().lstrip("./")
        if lookup in image_map:
            return f'{prefix}{quote}file://{image_map[lookup]}{quote}{suffix}'
        return match.group(0)

    # Rewrite src="..." and src='...' attributes
    html_content = re.sub(
        r'''(src\s*=\s*["'])([^"']+)(["'])''',
        _replace_src,
        html_content,
        flags=re.IGNORECASE,
    )

    # Rewrite CSS url(...) references
    html_content = re.sub(
        r'''(url\s*\()(['"]?)([^)'"]+)(['"]?\))''',
        _replace_css_url,
        html_content,
        flags=re.IGNORECASE,
    )

    return html_content


def _send_email(to: str, filename: str, subject_line: str, pdf_url: str, review: dict) -> None:
    """Send SES email with review summary and PDF download link."""
    score = review.get("overall_score")
    counts = review.get("issue_counts", {})
    summary = review.get("overall_summary", "")
    campaign_info = f" — <em>{subject_line}</em>" if subject_line else ""

    score_color = "#166534" if (score or 0) >= 80 else "#92400e" if (score or 0) >= 60 else "#991b1b"
    score_html = (
        f'<span style="font-size:2rem;font-weight:700;color:{score_color}">{score}/100</span>'
        if score is not None else "<span>N/A</span>"
    )

    critical = counts.get("critical", 0)
    warnings = counts.get("warning", 0)
    infos = counts.get("info", 0)

    issues_html = ""
    for issue in review.get("issues", [])[:5]:  # top 5 in email
        sev = issue.get("severity", "info")
        sev_color = {"critical": "#991b1b", "warning": "#92400e", "info": "#1d4ed8"}.get(sev, "#374151")
        sev_bg = {"critical": "#fee2e2", "warning": "#fef3c7", "info": "#dbeafe"}.get(sev, "#f3f4f6")
        issues_html += f"""
        <tr>
          <td style="padding:8px 10px;border-bottom:1px solid #f3f4f6;">
            <span style="background:{sev_bg};color:{sev_color};padding:2px 8px;border-radius:99px;
                         font-size:11px;font-weight:600;text-transform:uppercase">{sev}</span>
          </td>
          <td style="padding:8px 10px;border-bottom:1px solid #f3f4f6;font-size:13px">
            <strong>{issue.get('title','')}</strong><br>
            <span style="color:#6b7280;font-size:12px">{issue.get('category','')}</span>
          </td>
        </tr>"""

    ses.send_email(
        Source=SES_FROM,
        Destination={"ToAddresses": [to]},
        Message={
            "Subject": {"Data": f"Email Review Complete{' — ' + subject_line if subject_line else ''} [{score}/100]"},
            "Body": {
                "Html": {
                    "Data": f"""
<!DOCTYPE html><html><body style="font-family:Inter,Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a2e">
<div style="background:#1a1a2e;padding:24px 32px;border-radius:8px 8px 0 0">
  <h1 style="color:white;font-size:18px;margin:0">Email Annotator</h1>
  <p style="color:#9ca3af;font-size:13px;margin:4px 0 0">Review complete{campaign_info}</p>
</div>
<div style="background:white;padding:28px 32px;border:1px solid #e5e7eb;border-top:none">
  <div style="display:flex;align-items:center;gap:24px;margin-bottom:20px">
    <div style="text-align:center">
      {score_html}
      <div style="font-size:11px;color:#6b7280;margin-top:2px">Quality Score</div>
    </div>
    <div style="flex:1">
      <p style="margin:0 0 8px;font-size:14px;line-height:1.5;color:#374151">{summary}</p>
      <div style="display:flex;gap:12px;font-size:12px">
        <span style="color:#991b1b"><strong>{critical}</strong> critical</span>
        <span style="color:#92400e"><strong>{warnings}</strong> warnings</span>
        <span style="color:#1d4ed8"><strong>{infos}</strong> info</span>
      </div>
    </div>
  </div>

  {'<table style="width:100%;border-collapse:collapse;margin-bottom:20px"><thead><tr><th style="text-align:left;padding:8px 10px;background:#f9fafb;font-size:12px;color:#6b7280;border-bottom:1px solid #e5e7eb">Severity</th><th style="text-align:left;padding:8px 10px;background:#f9fafb;font-size:12px;color:#6b7280;border-bottom:1px solid #e5e7eb">Issue</th></tr></thead><tbody>' + issues_html + '</tbody></table>' if issues_html else ''}

  <p style="margin:0 0 16px;font-size:13px;color:#6b7280">
    The full annotated PDF includes all issues with detailed recommendations.
  </p>
  <a href="{pdf_url}" style="display:inline-block;background:#e94560;color:white;padding:12px 28px;
     border-radius:7px;text-decoration:none;font-weight:600;font-size:14px">
    Download Annotated PDF
  </a>
  <p style="margin:16px 0 0;font-size:11px;color:#9ca3af">This link expires in 7 days.</p>
</div>
</body></html>"""
                }
            },
        },
    )


def _resp(status_code: int, body: dict) -> dict:
    """Build an API Gateway proxy response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
        },
        "body": json.dumps(body),
    }
