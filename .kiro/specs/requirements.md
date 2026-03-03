# Email Campaign Annotator — Requirements Specification

**Project:** Email Campaign Annotator
**Version:** 1.0
**Author:** Vamshi Damera
**Date:** March 03, 2026

---

## 1. Problem Statement

Email marketing teams at pharmaceutical agencies currently spend 10–15 minutes per campaign manually creating annotated PDF proofs. The process requires four separate tools (Outlook, Dreamweaver, Email on Acid, Adobe InDesign), involves manually extracting every hyperlink from the HTML source, taking desktop and mobile screenshots, and building a callout-annotated PDF in InDesign. This manual workflow is error-prone, time-consuming, and produces no structured quality record.

The goal of this project is to fully automate this process using AWS cloud services, AWS Bedrock LLMs, and a simple web application accessible to 5–10 internal users.

---

## 2. Functional Requirements

### 2.1 Authentication and Access Control

**REQ-AUTH-01:** The system shall authenticate users via Amazon Cognito using email and password.

**REQ-AUTH-02:** Self-registration shall be disabled. Users shall only be added by an administrator via the AWS CLI or Cognito console.

**REQ-AUTH-03:** All API endpoints shall require a valid Cognito JWT token. Unauthenticated requests shall return HTTP 401.

**REQ-AUTH-04:** The system shall support a maximum of 10 concurrent registered users.

### 2.2 File Upload

**REQ-UPLOAD-01:** Authenticated users shall be able to upload an HTML email file (`.html`) via the web application.

**REQ-UPLOAD-02:** The upload form shall accept an optional subject line field and an optional recipient email address override (defaulting to the authenticated user's email).

**REQ-UPLOAD-03:** The system shall validate that the uploaded file is valid HTML before processing. Files larger than 5 MB shall be rejected with a clear error message.

**REQ-UPLOAD-04:** Upon successful upload, the system shall return a job ID and begin processing immediately. The web application shall display a processing status indicator.

### 2.3 HTML Parsing and Link Extraction

**REQ-PARSE-01:** The system shall parse the uploaded HTML file using BeautifulSoup and extract all hyperlinks (`<a href>` elements).

**REQ-PARSE-02:** For each extracted link, the system shall capture: the full URL, the anchor text, and the surrounding HTML context (up to 150 characters).

**REQ-PARSE-03:** The system shall also extract: the email subject line (from `<title>` or meta tags), the preheader text, the presence of a viewport meta tag, the presence of JavaScript, the total image count, and the count of images missing `alt` attributes.

### 2.4 Link Classification via AWS Bedrock (Claude 3 Haiku)

**REQ-CLASSIFY-01:** The system shall send all extracted links to AWS Bedrock (Claude 3 Haiku model: `anthropic.claude-3-haiku-20240307-v1:0`) for classification.

**REQ-CLASSIFY-02:** Each link shall be classified with a human-readable label (e.g., "Primary CTA", "Prescribing Information", "Unsubscribe", "Privacy Policy") and a boolean `include` flag indicating whether the link should appear in the annotated PDF.

**REQ-CLASSIFY-03:** Links classified as `include: false` (font stylesheets, tracking pixels, duplicate links) shall be excluded from the PDF callout annotations.

**REQ-CLASSIFY-04:** Included links shall be assigned sequential letters (A, B, C, ...) as callout identifiers.

### 2.5 Email Quality Review via AWS Bedrock (Claude 3 Sonnet)

**REQ-REVIEW-01:** The system shall send the email HTML (first 8,000 characters) and extracted metadata to AWS Bedrock (Claude 3 Sonnet model: `anthropic.claude-3-sonnet-20240229-v1:0`) for a comprehensive quality review.

**REQ-REVIEW-02:** The review shall evaluate the email across six categories: Links, Accessibility, Compliance, Content, Deliverability, and Technical.

**REQ-REVIEW-03:** The review shall return a structured JSON response containing: an overall quality score (0–100), an overall summary, an issue count by severity (critical / warning / info), and a list of individual issues each containing a title, description, category, severity, affected element, and recommendation.

**REQ-REVIEW-04:** The system shall validate the Bedrock response and apply safe defaults if the model returns malformed JSON.

**REQ-REVIEW-05:** The review shall complete within 30 seconds under normal operating conditions.

### 2.6 Screenshot Generation

**REQ-SCREENSHOT-01:** The system shall render the HTML email in a headless Chromium browser using Playwright and capture two screenshots: desktop (1200 × 900 px) and mobile (390 × 844 px).

**REQ-SCREENSHOT-02:** Screenshots shall be captured after the page reaches a network-idle state to ensure all images and fonts are loaded.

**REQ-SCREENSHOT-03:** Both screenshots shall be stored as PNG files in Amazon S3 under the job's prefix.

### 2.7 Image Annotation

**REQ-ANNOTATE-01:** The system shall overlay lettered callout circles on the desktop screenshot at positions corresponding to each included link's location in the rendered email.

**REQ-ANNOTATE-02:** Each callout shall display the assigned letter (A, B, C, ...) in a clearly visible colour-contrasted circle.

**REQ-ANNOTATE-03:** A corresponding legend shall be generated listing each letter, its label, and its full URL.

### 2.8 PDF Generation

**REQ-PDF-01:** The system shall generate a multi-page PDF using ReportLab containing the following pages in order:

- **Page 1 — Review Report:** Quality score, overall summary, and all issues grouped by severity with colour coding (red for critical, amber for warning, blue for info).
- **Page 2 — Desktop View:** Annotated desktop screenshot with callout legend.
- **Page 3 — Mobile View:** Annotated mobile screenshot with callout legend.

**REQ-PDF-02:** The PDF shall include a header on every page showing the campaign filename, job ID, and generation timestamp.

**REQ-PDF-03:** The generated PDF shall be stored in Amazon S3 under the `pdfs/` prefix with a 7-day lifecycle policy.

**REQ-PDF-04:** A pre-signed S3 URL valid for 7 days shall be generated for the PDF and included in the delivery email.

### 2.9 Email Delivery via Amazon SES

**REQ-EMAIL-01:** Upon job completion, the system shall send an HTML email to the recipient address via Amazon SES.

**REQ-EMAIL-02:** The delivery email shall include: the quality score, the overall review summary, the top 5 issues with severity badges, and a prominent download button linking to the pre-signed PDF URL.

**REQ-EMAIL-03:** The email subject shall follow the format: `Email Review Complete — [Subject Line] [Score/100]`.

**REQ-EMAIL-04:** The SES sender address shall be configurable via the `SES_FROM_EMAIL` environment variable.

### 2.10 Job History

**REQ-HISTORY-01:** The system shall store a JSON job record in S3 under `history/{user_email}/{job_id}.json` upon job completion.

**REQ-HISTORY-02:** The job record shall contain: job ID, filename, subject line, processing timestamp, quality score, issue counts, review summary, and PDF URL.

**REQ-HISTORY-03:** Authenticated users shall be able to retrieve their job history via `GET /jobs`, which returns all job records for their email address sorted by most recent first.

**REQ-HISTORY-04:** The web application shall display job history with quality score badges and PDF download links.

---

## 3. Non-Functional Requirements

### 3.1 Performance

**REQ-PERF-01:** End-to-end processing time (upload to email delivery) shall not exceed 5 minutes under normal operating conditions.

**REQ-PERF-02:** The web application shall load within 3 seconds on a standard broadband connection.

**REQ-PERF-03:** The system shall support up to 10 concurrent job submissions without degradation.

### 3.2 Security

**REQ-SEC-01:** All data in transit shall be encrypted using TLS 1.2 or higher.

**REQ-SEC-02:** All data at rest in S3 shall be encrypted using AWS-managed keys (SSE-S3).

**REQ-SEC-03:** The S3 bucket shall have public access blocked. All file access shall be via pre-signed URLs only.

**REQ-SEC-04:** Lambda functions shall follow the principle of least privilege. Each function's IAM role shall grant only the permissions required for its specific tasks.

**REQ-SEC-05:** Cognito self-registration shall be disabled. User accounts shall only be created by administrators.

### 3.3 Availability and Reliability

**REQ-AVAIL-01:** The system shall target 99.9% availability, leveraging the inherent availability of AWS managed services (Lambda, S3, Cognito, API Gateway, SES).

**REQ-AVAIL-02:** Lambda functions shall have a concurrency limit of 10 to prevent runaway costs.

**REQ-AVAIL-03:** Bedrock API failures shall be handled gracefully. If the classifier fails, links shall receive fallback labels. If the reviewer fails, the PDF shall be generated without a review report page and the user shall be notified.

### 3.4 Cost

**REQ-COST-01:** The total monthly AWS cost for 100 campaigns per month shall not exceed $5 USD.

**REQ-COST-02:** The system shall use AWS Lambda (serverless) rather than always-on compute to minimise idle costs.

### 3.5 Maintainability

**REQ-MAINT-01:** All infrastructure shall be defined as code using the AWS CDK (Python).

**REQ-MAINT-02:** All backend Python modules shall be independently testable with unit tests.

**REQ-MAINT-03:** Environment-specific configuration (S3 bucket name, SES sender, Bedrock model IDs) shall be managed via Lambda environment variables, not hardcoded.

---

## 4. Constraints and Assumptions

| Constraint / Assumption | Detail |
|---|---|
| User count | Maximum 10 registered users; no public access |
| Input format | HTML files only; no EML, MSG, or MJML formats in v1 |
| Email client rendering | Screenshots represent a single Chromium render; not multi-client (Outlook, Gmail, Apple Mail) |
| AWS region | All services deployed in a single AWS region (default: `us-east-1`) |
| SES sandbox | SES must be moved out of sandbox mode before production use; verified sender domain required |
| Bedrock model access | Claude 3 Haiku and Claude 3 Sonnet must be enabled in the target AWS region via the Bedrock console |
| Amplify hosting | Frontend is hosted on AWS Amplify; a GitHub repository connection is required for CI/CD |

---

## 5. Out of Scope (v1)

The following capabilities are explicitly out of scope for version 1 and are documented for future consideration:

- Multi-client email rendering (Outlook, Gmail, Apple Mail) — addressed in Sprint 3 via Bedrock Data Automation MCP
- Live URL reachability checking — addressed in Sprint 1 via Linkinator MCP
- Brand and compliance RAG review — addressed in Sprint 1 via Bedrock Knowledge Bases MCP
- CRM integration (HubSpot, Salesforce Marketing Cloud) — addressed in Sprint 4
- Async job queue — addressed in Sprint 2 via SNS/SQS MCP
- User self-service account management
- Campaign comparison or diff between versions
