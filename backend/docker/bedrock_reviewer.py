"""
bedrock_reviewer.py

Uses AWS Bedrock (Claude 3 Sonnet) to perform a comprehensive quality review
of an HTML email campaign. Returns a structured report with issues grouped by
severity and category, plus an overall score and executive summary.
"""

import json
import boto3
from bs4 import BeautifulSoup

bedrock = boto3.client("bedrock-runtime")

# Claude 3 Sonnet — more capable than Haiku, better for nuanced review tasks
REVIEW_MODEL = "anthropic.claude-3-sonnet-20240229-v1:0"

SYSTEM_PROMPT = """You are a senior email marketing quality assurance specialist with deep expertise in:
- HTML email development and rendering across clients
- Email accessibility (WCAG 2.1)
- CAN-SPAM, GDPR, and pharmaceutical marketing compliance
- Email deliverability and spam filter avoidance
- Copywriting and user experience best practices

You will receive the full HTML source of an email campaign and a list of all its hyperlinks.
Your task is to perform a thorough quality review and return a structured JSON report.

The report must follow this exact schema:
{
  "overall_score": <integer 0-100>,
  "overall_summary": "<2-3 sentence executive summary of the email quality>",
  "issue_counts": {
    "critical": <int>,
    "warning": <int>,
    "info": <int>
  },
  "issues": [
    {
      "id": "<short_snake_case_id>",
      "severity": "critical" | "warning" | "info",
      "category": "Links" | "Accessibility" | "Compliance" | "Content" | "Deliverability" | "Technical",
      "title": "<short issue title>",
      "description": "<detailed explanation of the issue and why it matters>",
      "recommendation": "<specific, actionable fix>",
      "element": "<the specific HTML snippet or URL that has the issue, or null>"
    }
  ]
}

Severity definitions:
- critical: Will cause the email to fail, be blocked, or violate legal requirements. Must fix before sending.
- warning: Degrades user experience, accessibility, or deliverability. Should fix.
- info: Best practice suggestion. Nice to have.

Review categories and what to check:

LINKS:
- URLs that appear broken, use placeholder text (e.g. "http://example.com", "#", "URL_HERE")
- Links missing UTM tracking parameters
- Links that open in a new tab without rel="noopener noreferrer"
- Duplicate links pointing to different URLs for the same anchor text
- Unsubscribe link presence (CAN-SPAM requirement)

ACCESSIBILITY:
- <img> tags missing alt attributes or with empty alt text on meaningful images
- Links with non-descriptive anchor text ("click here", "read more", "here")
- Missing or inadequate color contrast (flag if inline styles show very light text)
- Tables used for layout without role="presentation"
- Missing lang attribute on <html> tag

COMPLIANCE:
- Missing unsubscribe link or mechanism
- Missing physical mailing address (CAN-SPAM)
- Missing "Advertisement" or "Promotional" disclosure if required
- For pharmaceutical emails: check for required safety/prescribing information links
- Deceptive subject line indicators in preheader text

CONTENT:
- Broken or placeholder text (e.g. "Lorem ipsum", "[FIRST NAME]", "INSERT TEXT HERE")
- Excessive use of ALL CAPS (spam trigger)
- Excessive exclamation marks (spam trigger)
- Subject line / preheader mismatch or redundancy
- Missing or weak call-to-action

DELIVERABILITY:
- Spam trigger words in visible text (free, guarantee, no risk, act now, limited time, etc.)
- Image-to-text ratio heavily skewed toward images (likely to be blocked)
- Missing plain-text version indicator
- Excessively large HTML file size

TECHNICAL:
- Inline CSS missing on elements (email clients strip <style> blocks)
- Use of CSS properties not supported in major email clients (flexbox, grid, CSS variables)
- Missing viewport meta tag for mobile rendering
- Nested tables deeper than 4 levels
- Use of JavaScript (blocked by all email clients)
- Use of <video> or <audio> tags without fallback
- HTML file size concerns

Return ONLY the JSON object. No markdown, no explanation outside the JSON."""


def review_email(html_content: str, links: list[dict], subject: str = "", preheader: str = "") -> dict:
    """
    Sends the email HTML and link list to Claude 3 Sonnet for a comprehensive review.
    Returns a structured review report dict.
    """
    # Build a clean summary of the email for the LLM
    soup = BeautifulSoup(html_content, "lxml")

    # Extract visible text (truncated to avoid token limits)
    visible_text = soup.get_text(separator=" ", strip=True)[:3000]

    # Summarize images
    images = soup.find_all("img")
    img_summary = [
        {"src": img.get("src", "")[:80], "alt": img.get("alt"), "has_alt": img.has_attr("alt")}
        for img in images[:30]
    ]

    # Check for key structural elements
    has_unsubscribe = any(
        "unsub" in (l.get("url", "") + l.get("anchor_text", "")).lower()
        for l in links
    )
    has_view_online = any(
        any(kw in (l.get("url", "") + l.get("anchor_text", "")).lower()
            for kw in ["view", "online", "browser", "web version"])
        for l in links
    )
    html_lang = soup.find("html")
    lang_attr = html_lang.get("lang") if html_lang else None
    has_viewport = bool(soup.find("meta", attrs={"name": "viewport"}))
    has_js = bool(soup.find("script"))
    html_size_kb = round(len(html_content.encode("utf-8")) / 1024, 1)

    # Count images without alt text
    imgs_missing_alt = sum(1 for img in images if not img.has_attr("alt"))

    context = {
        "subject_line": subject,
        "preheader_text": preheader,
        "html_size_kb": html_size_kb,
        "has_unsubscribe_link": has_unsubscribe,
        "has_view_online_link": has_view_online,
        "html_lang_attribute": lang_attr,
        "has_viewport_meta": has_viewport,
        "has_javascript": has_js,
        "total_images": len(images),
        "images_missing_alt": imgs_missing_alt,
        "total_links": len(links),
        "links": [{"url": l["url"][:100], "anchor_text": l["anchor_text"][:60]} for l in links[:40]],
        "image_details": img_summary,
        "visible_text_sample": visible_text,
    }

    # Truncate HTML for the LLM — send first 8000 chars which covers most email structure
    html_sample = html_content[:8000]

    user_message = f"""Please review this email campaign.

METADATA:
{json.dumps(context, indent=2)}

HTML SOURCE (first 8000 characters):
{html_sample}
"""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}],
        "temperature": 0.1,
    })

    try:
        resp = bedrock.invoke_model(modelId=REVIEW_MODEL, body=body)
        raw = json.loads(resp["body"].read())["content"][0]["text"]

        # Strip any accidental markdown code fences
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        report = json.loads(raw)
        return _validate_report(report)

    except Exception as e:
        print(f"[WARN] Bedrock review failed: {e}")
        return _fallback_report(str(e))


def _validate_report(report: dict) -> dict:
    """Ensure the report has all required fields with safe defaults."""
    report.setdefault("overall_score", 0)
    report.setdefault("overall_summary", "Review could not be completed.")
    report.setdefault("issue_counts", {"critical": 0, "warning": 0, "info": 0})
    report.setdefault("issues", [])

    # Recount from actual issues list to ensure consistency
    counts = {"critical": 0, "warning": 0, "info": 0}
    for issue in report["issues"]:
        sev = issue.get("severity", "info")
        if sev in counts:
            counts[sev] += 1
        issue.setdefault("element", None)
        issue.setdefault("category", "Technical")
    report["issue_counts"] = counts

    return report


def _fallback_report(error_msg: str) -> dict:
    return {
        "overall_score": None,
        "overall_summary": f"Automated review could not be completed: {error_msg}",
        "issue_counts": {"critical": 0, "warning": 0, "info": 0},
        "issues": [],
    }
