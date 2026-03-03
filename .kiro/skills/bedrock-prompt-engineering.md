# Skill: Bedrock Prompt Engineering for Email Analysis

**Skill ID:** bedrock-prompt-engineering
**Applies to:** `bedrock_classifier.py`, `bedrock_reviewer.py`, and any future Bedrock modules
**Last updated:** March 03, 2026

---

## Overview

This skill defines the patterns, templates, and best practices for writing effective prompts for the two AWS Bedrock Claude models used in this pipeline. It is the authoritative reference for anyone modifying or extending the AI capabilities of the Email Campaign Annotator.

---

## Skill 1: Link Classification Prompts (Claude 3 Haiku)

### When to use this skill

Use this skill when modifying the system prompt in `bedrock_classifier.py` or when adding a new classification task that needs to categorise links, images, or other HTML elements.

### The Classification Prompt Pattern

An effective classification prompt for Claude 3 Haiku has four components: a role definition, a task description with output schema, a list of label examples, and a strict JSON-only instruction.

```python
SYSTEM = """You are an email marketing analyst specialising in pharmaceutical campaigns.

Classify each hyperlink from an HTML email campaign. For every link return:
- label: short human-readable label describing the link's purpose
- include: true for user-facing content links; false for technical/tracking links

Label examples by category:
  Navigation: "Header Logo", "View Online", "Footer Logo"
  CTAs: "Primary CTA", "Secondary CTA", "Learn More"
  Regulatory: "Prescribing Information", "Full Prescribing Information", "ISI"
  Legal: "Privacy Policy", "Terms & Conditions", "Cookie Policy"
  Compliance: "Unsubscribe", "Manage Preferences", "Physical Address"
  Social: "Facebook", "Twitter/X", "LinkedIn", "Instagram"
  Support: "Contact Us", "Customer Service", "Medical Information"

Set include=false for: font CDN links, tracking pixel URLs, duplicate links,
  CSS stylesheet links, or any URL containing "track", "pixel", "open.aspx".

Return ONLY valid JSON: {"links": [{"label": "...", "include": true/false}, ...]}
One entry per input link, same order as input. No preamble. No explanation."""
```

### Extending the Label Taxonomy

When the agency adds a new campaign type (e.g., patient support programs, HCP portals), extend the label examples section with new category entries. Do not remove existing categories. The model learns from the examples, so more specific examples produce more accurate labels.

### Handling Multi-Language Emails

If the email contains non-English content, add the following instruction to the system prompt: "If anchor text is in a language other than English, translate the label to English." This ensures consistent labelling across all campaigns.

---

## Skill 2: Quality Review Prompts (Claude 3 Sonnet)

### When to use this skill

Use this skill when modifying the system prompt in `bedrock_reviewer.py`, when adding new review categories, or when integrating the Bedrock Knowledge Bases MCP for brand-aware review.

### The Review Prompt Pattern

An effective review prompt for Claude 3 Sonnet has five components: a role definition, a review scope definition, an output schema with field descriptions, category-specific review criteria, and a scoring rubric.

```python
SYSTEM_PROMPT = """You are a senior email marketing QA specialist with expertise in
pharmaceutical email compliance, accessibility standards, and email deliverability.

Review the provided HTML email campaign and return a structured JSON quality report.

OUTPUT SCHEMA (return ONLY this JSON, no preamble):
{
  "overall_score": <integer 0-100>,
  "overall_summary": "<2-3 sentence plain-English summary>",
  "issue_counts": {"critical": <int>, "warning": <int>, "info": <int>},
  "issues": [
    {
      "title": "<short issue title>",
      "description": "<what the problem is>",
      "category": "<Links|Accessibility|Compliance|Content|Deliverability|Technical>",
      "severity": "<critical|warning|info>",
      "element": "<affected HTML element or null>",
      "recommendation": "<specific actionable fix>"
    }
  ]
}

REVIEW CRITERIA BY CATEGORY:

Links — critical: broken/placeholder URLs (href="#", href="URL_HERE"), missing unsubscribe link.
  warning: links without UTM parameters, redirect chains > 2 hops, non-HTTPS URLs.
  info: link text not descriptive ("click here", "here"), duplicate destination URLs.

Accessibility — critical: images with empty alt="" that convey meaning, missing lang attribute.
  warning: images missing alt attribute entirely, non-descriptive link text, low contrast text.
  info: missing title attribute on images, decorative images without alt="".

Compliance — critical: missing CAN-SPAM physical address, missing unsubscribe mechanism.
  warning: missing view-online link, prescribing information link not prominent.
  info: missing preheader text, subject line > 60 characters.

Content — critical: placeholder text present ([FIRST NAME], TBD, Lorem ipsum, [INSERT]).
  warning: ALL CAPS words > 3 characters, excessive exclamation marks (> 3).
  info: weak CTA text ("Submit", "Click"), subject line spam trigger words.

Deliverability — critical: HTML file > 100 KB, spam trigger words in subject line.
  warning: image-to-text ratio > 80% images, HTML file > 60 KB.
  info: missing preheader, subject line > 50 characters.

Technical — critical: JavaScript present (<script> tags), CSS using flexbox or grid.
  warning: missing viewport meta tag, inline styles using !important.
  info: deprecated HTML attributes (bgcolor, align, valign), tables > 600px wide.

SCORING RUBRIC:
90-100: Excellent — no critical issues, ≤ 2 warnings
75-89:  Good — no critical issues, ≤ 5 warnings
60-74:  Fair — no critical issues, > 5 warnings or ≤ 2 critical
40-59:  Poor — 3-5 critical issues
0-39:   Failing — > 5 critical issues or fundamental compliance failure"""
```

### Adding a New Review Category

To add a new review category (e.g., "Brand Compliance" for Sprint 1 Bedrock Knowledge Bases integration):

1. Add the new category name to the `category` enum in the output schema.
2. Add a new section to the REVIEW CRITERIA section with critical/warning/info rules.
3. Update `_validate_report()` in `bedrock_reviewer.py` to accept the new category name.
4. Update the PDF builder's category colour mapping if a new colour is needed.
5. Update `requirements.md` with the new review category.

### Injecting RAG Context (Sprint 1 — Bedrock Knowledge Bases MCP)

When the Bedrock Knowledge Bases MCP is integrated, the retrieved brand guidelines are injected into the user message before the HTML sample:

```python
user_message = f"""BRAND GUIDELINES (retrieved from knowledge base):
{retrieved_context}

Please review this email campaign against these guidelines and the standard criteria.

METADATA:
{json.dumps(context, indent=2)}

HTML SOURCE (first 8000 characters):
{html_sample}
"""
```

The system prompt remains unchanged. The brand context is provided as user-turn content to keep the system prompt stable and cacheable.

---

## Skill 3: Structured Output Reliability

### The JSON Fence Stripping Pattern

Claude models occasionally wrap JSON output in markdown code fences despite being instructed not to. Always apply this stripping pattern after receiving the model's response:

```python
raw = raw.strip()
if raw.startswith("```"):
    raw = raw.split("```")[1]
    if raw.startswith("json"):
        raw = raw[4:]
raw = raw.strip()
result = json.loads(raw)
```

### The Validation + Fallback Pattern

Every Bedrock response must pass through a validation function before use. The validation function applies `setdefault()` for every required field and recomputes derived fields. The fallback function returns a complete safe object when the Bedrock call fails entirely.

```python
def _validate_report(report: dict) -> dict:
    report.setdefault("overall_score", 0)
    report.setdefault("overall_summary", "Review could not be completed.")
    report.setdefault("issues", [])
    # Recount from actual issues — never trust the model's count
    counts = {"critical": 0, "warning": 0, "info": 0}
    for issue in report["issues"]:
        sev = issue.get("severity", "info")
        if sev in counts:
            counts[sev] += 1
        issue.setdefault("element", None)
        issue.setdefault("recommendation", "No recommendation provided.")
    report["issue_counts"] = counts
    return report

def _fallback_report(error_msg: str) -> dict:
    return {
        "overall_score": None,
        "overall_summary": f"Automated review could not be completed: {error_msg}",
        "issue_counts": {"critical": 0, "warning": 0, "info": 0},
        "issues": [],
    }
```

---

## Skill 4: Prompt Testing Methodology

Before deploying a modified prompt to production, test it against the following three email types:

| Test Case | File | Expected Behaviour |
|---|---|---|
| Clean email | `tests/fixtures/clean_email.html` | Score ≥ 85, ≤ 2 warnings, 0 critical |
| Broken links | `tests/fixtures/broken_links_email.html` | ≥ 2 critical link issues detected |
| Missing compliance | `tests/fixtures/no_unsubscribe_email.html` | Critical compliance issue for missing unsubscribe |
| Placeholder text | `tests/fixtures/placeholder_email.html` | Critical content issue for `[FIRST NAME]` placeholder |
| Heavy image email | `tests/fixtures/image_heavy_email.html` | Warning for image-to-text ratio |

Run these tests using the `tests/integration/test_bedrock_reviewer.py` integration test with mocked Bedrock responses, and periodically against the live Bedrock API to catch model behaviour changes.
