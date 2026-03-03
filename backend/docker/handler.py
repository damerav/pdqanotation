import json
import os
import uuid
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


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}"))

    html_content = body.get("html_content", "")
    filename = body.get("filename", "email.html")
    subject_line = body.get("subject_line", "")
    preheader_text = body.get("preheader_text", "")
    recipient_email = body.get("recipient_email", "")

    if not html_content or not recipient_email:
        return _resp(400, {"error": "html_content and recipient_email are required."})

    job_id = str(uuid.uuid4())[:8]
    s3_prefix = f"jobs/{job_id}"

    try:
        # 1. Parse all links from HTML
        raw_links = extract_links(html_content)

        # 2. Bedrock Call #1 — Classify links (Claude 3 Haiku, fast + cheap)
        classified = classify_links(raw_links)

        # 3. Bedrock Call #2 — Full email quality review (Claude 3 Sonnet, thorough)
        review = review_email(html_content, raw_links, subject_line, preheader_text)

        # 4. Screenshots via Playwright headless Chromium
        desktop_bytes, mobile_bytes = capture_screenshots(html_content)

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
        pdf_key = f"{s3_prefix}/{filename.replace('.html', '')}_annotated.pdf"
        s3.put_object(Bucket=BUCKET, Key=pdf_key, Body=pdf_bytes, ContentType="application/pdf")

        # 8. Generate pre-signed URL (7-day expiry)
        pdf_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": BUCKET, "Key": pdf_key},
            ExpiresIn=604800,
        )

        # 9. Send SES email with review summary + PDF link
        _send_email(recipient_email, filename, subject_line, pdf_url, review)

        # 10. Persist job record (includes review summary for History page)
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
            Key=f"history/{recipient_email}/{job_id}.json",
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


def _send_email(to, filename, subject_line, pdf_url, review):
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


def _resp(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
        },
        "body": json.dumps(body),
    }
