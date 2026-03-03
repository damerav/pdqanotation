# Skill: MCP Server Integration

**Skill ID:** mcp-integration
**Applies to:** All pipeline modules in `backend/docker/` and the CDK infrastructure stack
**Last updated:** March 03, 2026

---

## Overview

This skill defines how to integrate Model Context Protocol (MCP) servers into the Email Campaign Annotator pipeline. It covers the 8 planned MCP integrations across 4 sprints, with implementation patterns for each. Before implementing any new feature, consult this skill to determine whether an MCP server is the appropriate approach.

---

## What is MCP?

The Model Context Protocol (MCP) is an open standard that allows AI agents and applications to connect to external tools and data sources through a standardised interface. In this project, MCP servers act as specialised capability providers that the Lambda processor can call to perform specific tasks — replacing custom-built code with maintained, purpose-built integrations.

---

## Sprint 1 Integrations (Highest Priority)

### MCP-01: Linkinator MCP — Live URL Validation

**Replaces:** HTML-only link extraction (no live validation currently exists)
**Module to update:** `html_parser.py`
**Impact:** Adds HTTP status checking for every extracted URL before classification

The Linkinator MCP checks whether each URL in the email is reachable and returns its HTTP status code, redirect chain, and final destination URL. This is the single highest-value addition because it catches broken links that the current system cannot detect.

**Integration pattern:**

```python
# In html_parser.py — add after link extraction
from mcp_client import MCPClient

def validate_links_live(links: list[dict]) -> list[dict]:
    """Check HTTP reachability of all extracted links via Linkinator MCP."""
    client = MCPClient("linkinator")
    for link in links:
        try:
            result = client.call("check", {"url": link["url"], "timeout": 5000})
            link["http_status"] = result.get("status")
            link["is_broken"] = result.get("status", 200) >= 400
            link["redirect_url"] = result.get("finalUrl", link["url"])
        except Exception:
            link["http_status"] = None
            link["is_broken"] = None
    return links
```

**CDK update required:** Add the Linkinator MCP endpoint URL as a Lambda environment variable. No additional IAM permissions required (outbound HTTPS is allowed by default).

**Bedrock reviewer update required:** Pass `is_broken: true` links as pre-identified critical issues to the reviewer, reducing the reviewer's need to infer broken links from URL patterns.

---

### MCP-02: Playwright MCP — Screenshot Service

**Replaces:** Custom Playwright code in `screenshot_generator.py`
**Module to update:** `screenshot_generator.py`
**Impact:** Removes Chromium from the Lambda container, reducing image size by ~40% and cold start time by ~15 seconds

The Playwright MCP provides a managed browser service that accepts HTML content and viewport parameters and returns a screenshot. This removes the need to bundle Chromium inside the Lambda container.

**Integration pattern:**

```python
# Replace screenshot_generator.py with this pattern
from mcp_client import MCPClient

def capture_screenshots(html_content: str) -> tuple[bytes, bytes]:
    """Capture desktop and mobile screenshots via Playwright MCP."""
    client = MCPClient("playwright")
    
    desktop = client.call("screenshot", {
        "html": html_content,
        "viewport": {"width": 1200, "height": 900},
        "waitUntil": "networkidle",
        "format": "png"
    })
    
    mobile = client.call("screenshot", {
        "html": html_content,
        "viewport": {"width": 390, "height": 844},
        "waitUntil": "networkidle",
        "format": "png",
        "isMobile": True
    })
    
    return desktop["imageData"], mobile["imageData"]
```

**CDK update required:** Reduce Lambda memory from 3,008 MB to 1,024 MB after removing Chromium. Update the Dockerfile to remove Playwright and Chromium installation steps. Add the Playwright MCP endpoint URL as a Lambda environment variable.

---

### MCP-03: Bedrock Knowledge Bases MCP — Brand-Aware Review

**Replaces:** Generic system prompt in `bedrock_reviewer.py`
**Module to update:** `bedrock_reviewer.py`
**Impact:** Makes the AI reviewer brand-aware by injecting relevant brand guidelines, approved claims, and regulatory documents into each review call

**Knowledge base content to upload:**
- Brand voice and tone guidelines
- Approved product claims library
- Regulatory submission requirements (ISI placement, font size rules)
- CAN-SPAM and CASL compliance checklist
- Agency-specific style guide

**Integration pattern:**

```python
# In bedrock_reviewer.py — add before the Bedrock call
from mcp_client import MCPClient

def retrieve_brand_context(subject_line: str, html_sample: str) -> str:
    """Retrieve relevant brand guidelines from the knowledge base."""
    client = MCPClient("bedrock-knowledge-bases")
    query = f"Email campaign guidelines for: {subject_line}"
    result = client.call("retrieve", {
        "knowledgeBaseId": os.environ["KNOWLEDGE_BASE_ID"],
        "retrievalQuery": {"text": query},
        "retrievalConfiguration": {
            "vectorSearchConfiguration": {"numberOfResults": 5}
        }
    })
    chunks = [r["content"]["text"] for r in result.get("retrievalResults", [])]
    return "\n\n".join(chunks)
```

**CDK update required:** Add `KNOWLEDGE_BASE_ID` as a Lambda environment variable. Add `bedrock:Retrieve` and `bedrock:RetrieveAndGenerate` to the Processor Lambda's IAM policy.

---

## Sprint 2 Integrations

### MCP-04: CloudWatch MCP — Custom Metrics and Alarms

**Adds:** Structured operational metrics for each pipeline stage
**Module to update:** `handler.py`
**Impact:** Enables dashboards and alarms for error rates, processing times, and review score distributions

**Metrics to emit:**

| Metric Name | Unit | Description |
|---|---|---|
| `JobsSubmitted` | Count | Total jobs submitted |
| `JobsCompleted` | Count | Jobs completed successfully |
| `JobsFailed` | Count | Jobs that threw an exception |
| `ProcessingDurationMs` | Milliseconds | End-to-end pipeline duration |
| `BedrockClassifierDurationMs` | Milliseconds | Classifier call duration |
| `BedrockReviewerDurationMs` | Milliseconds | Reviewer call duration |
| `ReviewScore` | None | Quality score per job (0–100) |
| `CriticalIssuesFound` | Count | Critical issues per job |

**Integration pattern:**

```python
# In handler.py — wrap each pipeline stage
import time
from mcp_client import MCPClient

cw = MCPClient("cloudwatch")

def emit_metric(name: str, value: float, unit: str = "Count"):
    cw.call("put_metric_data", {
        "Namespace": "EmailAnnotator",
        "MetricData": [{"MetricName": name, "Value": value, "Unit": unit}]
    })

# Usage in pipeline
t0 = time.time()
review = review_email(html_content, links, subject_line)
emit_metric("BedrockReviewerDurationMs", (time.time() - t0) * 1000, "Milliseconds")
emit_metric("ReviewScore", review.get("overall_score", 0))
```

---

### MCP-05: SNS/SQS MCP — Async Job Queue

**Replaces:** Synchronous Lambda invocation via API Gateway
**Modules to update:** `handler.py` (split into submitter + processor), `annotator_stack.py`
**Impact:** Eliminates the 29-second API Gateway timeout constraint; allows jobs to run for the full 5-minute Lambda timeout without the user waiting

**Architecture change:** The POST /process endpoint becomes a job submitter that publishes to an SQS queue and immediately returns a job ID. A separate SQS-triggered Lambda processes the job asynchronously. The frontend polls GET /jobs to check completion status.

**This is a significant architectural change** — implement only after the Sprint 1 improvements are stable and tested.

---

## Sprint 3 Integration

### MCP-06: Bedrock Data Automation MCP — Visual Review

**Adds:** Screenshot-based visual quality review
**Module to update:** `bedrock_reviewer.py` (add a second review pass)
**Impact:** Detects visual issues invisible in HTML: contrast failures, broken image layouts, small tap targets, text overflow

**Integration pattern:** After screenshots are captured, pass them to Bedrock's multimodal capability via the Data Automation MCP for a visual review pass. The visual review results are merged with the HTML review results before PDF generation.

---

## Sprint 4 Integration

### MCP-07: HubSpot / Salesforce Marketing Cloud MCP — CRM Record

**Adds:** Automatic PDF attachment to the campaign record in the CRM
**Module to update:** `handler.py` (add CRM call after SES delivery)
**Impact:** Creates a permanent audit trail linking the annotated PDF proof to the campaign record

**Configuration required:** CRM API credentials stored in AWS Secrets Manager (not Lambda environment variables, as these are genuinely secret). Add `secretsmanager:GetSecretValue` to the Processor Lambda's IAM policy.

---

## General MCP Integration Guidelines

When implementing any MCP integration, follow these patterns consistently:

**Error isolation:** Wrap every MCP call in a try/except. MCP failures must never abort the main pipeline. If an MCP call fails, log the error, use a fallback value, and continue processing.

**Timeout handling:** Set a timeout on every MCP call. The total Lambda timeout is 5 minutes. Allocate no more than 30 seconds to any single MCP call.

**Environment variable naming:** MCP endpoint URLs and configuration values follow the pattern `MCP_{SERVER_NAME}_{PARAM}` (e.g., `MCP_PLAYWRIGHT_ENDPOINT`, `MCP_KB_KNOWLEDGE_BASE_ID`).

**CDK pattern for MCP endpoints:**

```python
# In annotator_stack.py — add MCP endpoint as environment variable
processor_fn = lambda_.DockerImageFunction(
    self, "ProcessorFn",
    environment={
        "S3_BUCKET": bucket.bucket_name,
        "SES_FROM_EMAIL": ses_from_email,
        "MCP_PLAYWRIGHT_ENDPOINT": playwright_mcp_endpoint,  # add new MCP vars here
    }
)
```
