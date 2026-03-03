# Email Campaign Annotator — Technical Design Specification

**Project:** Email Campaign Annotator
**Version:** 1.0
**Author:** Vamshi Damera
**Date:** March 03, 2026

---

## 1. System Architecture Overview

The Email Campaign Annotator is a serverless, event-driven system built entirely on AWS managed services. It consists of three layers: a React single-page application hosted on AWS Amplify, a REST API backed by AWS API Gateway and AWS Lambda, and a storage and AI layer using Amazon S3, AWS Bedrock, and Amazon SES.

```
┌─────────────────────────────────────────────────────────────────┐
│  CLIENT LAYER                                                   │
│  React SPA (AWS Amplify + CloudFront)                           │
│  Authentication: Amazon Cognito (email + password, no self-reg) │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS + Cognito JWT
┌────────────────────────────▼────────────────────────────────────┐
│  API LAYER                                                      │
│  Amazon API Gateway (REST)                                      │
│  POST /process  →  Processor Lambda (Docker, 3 GB, 5 min)      │
│  GET  /jobs     →  Jobs Lambda (ZIP, 128 MB, 15 s)             │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  PROCESSING LAYER                                               │
│  Processor Lambda (8 sequential pipeline steps)                 │
│  ├── html_parser.py       BeautifulSoup link + metadata extract │
│  ├── bedrock_classifier.py  Claude 3 Haiku link classification  │
│  ├── bedrock_reviewer.py    Claude 3 Sonnet quality review      │
│  ├── screenshot_generator.py  Playwright desktop + mobile       │
│  ├── image_annotator.py    Pillow callout overlay               │
│  ├── pdf_builder.py        ReportLab 3-page PDF                 │
│  └── handler.py            Orchestrator + S3 + SES              │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  DATA LAYER                                                     │
│  Amazon S3 (single bucket, 3 prefixes)                          │
│  ├── uploads/{job_id}/input.html                                │
│  ├── pdfs/{job_id}/annotated.pdf  (7-day lifecycle)             │
│  └── history/{user_email}/{job_id}.json                         │
│                                                                 │
│  AWS Bedrock                                                    │
│  ├── anthropic.claude-3-haiku-20240307-v1:0  (classifier)      │
│  └── anthropic.claude-3-sonnet-20240229-v1:0 (reviewer)        │
│                                                                 │
│  Amazon SES  (delivery email with PDF link)                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Design

### 2.1 Frontend — React SPA

**Framework:** React 18 with Vite build tooling
**Hosting:** AWS Amplify (auto-deploys from GitHub on push to `main`)
**Authentication:** `@aws-amplify/ui-react` `<Authenticator>` component with Cognito

The application has two pages:

| Page | Route | Component | Description |
|---|---|---|---|
| New Job | `/` (default) | `UploadPage.jsx` | File upload form, job submission, result display |
| History | `/history` | `HistoryPage.jsx` | Past jobs list with scores and PDF links |

**State management:** React `useState` only — no Redux or Zustand required given the small scope.

**API calls:** All calls use the Amplify `fetchAuthSession()` helper to obtain the Cognito JWT, which is passed as a `Bearer` token in the `Authorization` header to API Gateway.

### 2.2 API Gateway

Two REST resources are exposed:

| Method | Path | Lambda | Auth | Description |
|---|---|---|---|---|
| `POST` | `/process` | Processor Lambda | Cognito JWT | Submit HTML file for processing |
| `GET` | `/jobs` | Jobs Lambda | Cognito JWT | Retrieve job history for authenticated user |
| `OPTIONS` | `/*` | (CORS preflight) | None | CORS preflight response |

CORS is configured to allow all origins (`*`) with `Authorization` and `Content-Type` headers. In production, this should be restricted to the Amplify CloudFront domain.

### 2.3 Processor Lambda

**Runtime:** Docker container (Python 3.11 + Playwright + Chromium + ReportLab + Pillow)
**Memory:** 3,008 MB (required for Chromium)
**Timeout:** 5 minutes
**Concurrency limit:** 10

The handler (`handler.py`) orchestrates the pipeline in the following sequence:

```
1. Parse request body → extract html_content, recipient_email, subject_line
2. html_parser.py     → extract links + metadata
3. bedrock_classifier.py → classify links via Claude 3 Haiku
4. bedrock_reviewer.py   → review email via Claude 3 Sonnet
5. screenshot_generator.py → capture desktop + mobile PNG via Playwright
6. image_annotator.py    → overlay callout letters on desktop screenshot
7. pdf_builder.py        → build 3-page PDF (review + desktop + mobile)
8. S3 upload             → store PDF, return pre-signed URL
9. SES send              → deliver email with score + PDF link
10. S3 job record        → store JSON history record
```

**Error handling:** Each step is wrapped in a try/except. Bedrock failures produce fallback outputs (default labels, empty review). Playwright failures propagate as 500 errors. All errors are logged to CloudWatch.

### 2.4 HTML Parser (`html_parser.py`)

Extracts the following from the HTML:

- All `<a href>` elements with URL, anchor text, and 150-character surrounding context
- Subject line from `<title>` tag or `og:title` meta
- Preheader text from the first visible `<p>` or `<td>` after the body open
- Viewport meta tag presence
- JavaScript presence (`<script>` tags)
- All `<img>` elements with `src`, `alt`, `width`, `height`
- Count of images missing `alt` attributes
- Visible text sample (first 2,000 characters of stripped text content)

### 2.5 Bedrock Classifier (`bedrock_classifier.py`)

**Model:** `anthropic.claude-3-haiku-20240307-v1:0`
**Max tokens:** 1,024
**Temperature:** default (0.7)

The classifier receives a JSON array of link objects and returns a JSON object with a `links` array. Each entry contains a `label` string and an `include` boolean. Links with `include: false` are filtered out before annotation. Included links are assigned sequential letters A–Z.

**Fallback:** If the Bedrock call fails, all links receive labels `Link 1`, `Link 2`, ... and `include: true`.

### 2.6 Bedrock Reviewer (`bedrock_reviewer.py`)

**Model:** `anthropic.claude-3-sonnet-20240229-v1:0`
**Max tokens:** 4,096
**Temperature:** 0.1 (low for consistent structured output)

The reviewer receives a structured metadata object and the first 8,000 characters of the HTML. It returns a JSON object with the following schema:

```json
{
  "overall_score": 0-100,
  "overall_summary": "string",
  "issue_counts": { "critical": 0, "warning": 0, "info": 0 },
  "issues": [
    {
      "title": "string",
      "description": "string",
      "category": "Links|Accessibility|Compliance|Content|Deliverability|Technical",
      "severity": "critical|warning|info",
      "element": "string|null",
      "recommendation": "string"
    }
  ]
}
```

**Validation:** The `_validate_report()` function applies safe defaults for all required fields and recounts issue severities from the actual issues list to ensure `issue_counts` is always accurate.

**Fallback:** If the Bedrock call fails or returns malformed JSON, a fallback report with `overall_score: null` and an empty issues list is returned. The PDF is still generated without a review page.

### 2.7 Screenshot Generator (`screenshot_generator.py`)

**Library:** Playwright (sync API, Chromium)
**Viewports:** Desktop 1200×900, Mobile 390×844

The generator uses `page.set_content()` to inject the HTML directly rather than navigating to a URL. This avoids network dependencies for locally-uploaded files. After setting content, it waits for `networkidle` to ensure all embedded resources are loaded before capturing the screenshot.

### 2.8 Image Annotator (`image_annotator.py`)

**Library:** Pillow (PIL)

The annotator overlays circular callout badges on the desktop screenshot. Each badge is positioned at the approximate vertical centre of the link's bounding box in the rendered page. The letter is drawn in white on a red (`#e94560`) filled circle of 28px diameter. A legend table is generated as a separate image listing all callout letters, labels, and truncated URLs.

### 2.9 PDF Builder (`pdf_builder.py`)

**Library:** ReportLab

The PDF is built as three pages:

**Page 1 — Review Report**
- Header bar with campaign name, job ID, and timestamp
- Quality score displayed as a large coloured number (green ≥ 80, amber ≥ 60, red < 60)
- Overall summary paragraph
- Issues table with severity colour coding: red rows for critical, amber for warning, blue for info
- Each row shows: severity badge, category, title, description, and recommendation

**Page 2 — Desktop View**
- Full-width annotated desktop screenshot (scaled to fit A4 landscape)
- Callout legend below the screenshot

**Page 3 — Mobile View**
- Mobile screenshot (scaled to fit A4 portrait)
- Same callout legend

### 2.10 Jobs Lambda (`jobs_handler.py`)

**Runtime:** Python 3.12 (ZIP deployment)
**Memory:** 128 MB
**Timeout:** 15 seconds

Lists all objects under `history/{user_email}/` in S3, reads each JSON file, and returns them sorted by `timestamp` descending. The user email is extracted from the Cognito JWT claims in the API Gateway request context (`requestContext.authorizer.claims.email`).

---

## 3. Data Models

### 3.1 Job Record (stored in S3 as JSON)

```json
{
  "job_id": "a1b2c3d4",
  "filename": "kerendia_q1_campaign.html",
  "subject_line": "Important Safety Information",
  "timestamp": "2026-03-03T15:30:00Z",
  "review_score": 82,
  "issue_counts": { "critical": 0, "warning": 3, "info": 5 },
  "review_summary": "The email meets most quality standards with minor accessibility improvements recommended.",
  "pdf_url": "https://s3.amazonaws.com/bucket/pdfs/a1b2c3d4/annotated.pdf?X-Amz-Expires=604800&..."
}
```

### 3.2 API Request — POST /process

```json
{
  "html_content": "<html>...</html>",
  "recipient_email": "user@pdqcomms.com",
  "subject_line": "Important Safety Information"
}
```

### 3.3 API Response — POST /process (200 OK)

```json
{
  "job_id": "a1b2c3d4",
  "pdf_url": "https://s3.amazonaws.com/...",
  "review_score": 82,
  "issue_counts": { "critical": 0, "warning": 3, "info": 5 },
  "review_summary": "The email meets most quality standards..."
}
```

---

## 4. Infrastructure as Code (AWS CDK)

All infrastructure is defined in `infrastructure/annotator_stack.py` using the AWS CDK (Python). The stack creates the following resources in a single `cdk deploy` command:

| Resource | Type | Key Configuration |
|---|---|---|
| `EmailAnnotatorBucket` | `aws_s3.Bucket` | Versioned, SSE-S3 encrypted, public access blocked, 7-day lifecycle on `pdfs/*` |
| `EmailAnnotatorUserPool` | `aws_cognito.UserPool` | Email sign-in, self-signup disabled, strong password policy |
| `EmailAnnotatorUserPoolClient` | `aws_cognito.UserPoolClient` | No client secret (SPA), auth flows: USER_SRP_AUTH |
| `ProcessorFn` | `aws_lambda.DockerImageFunction` | 3,008 MB, 5 min timeout, ECR image from `../backend/docker` |
| `JobsFn` | `aws_lambda.Function` | Python 3.12, 128 MB, 15 s timeout, ZIP from `../backend/lambda` |
| `AnnotatorApi` | `aws_apigateway.RestApi` | CORS enabled, Cognito JWT authorizer |
| `CognitoAuth` | `aws_apigateway.CognitoUserPoolsAuthorizer` | Attached to all non-OPTIONS methods |

**CDK Outputs** (used to configure `aws-config.js`):
- `UserPoolId`
- `UserPoolClientId`
- `ApiEndpoint`
- `BucketName`

---

## 5. Security Design

### 5.1 Authentication Flow

```
User → Amplify UI → Cognito Hosted UI → JWT (ID + Access tokens)
                                      ↓
                              Stored in browser memory
                                      ↓
                    API request → Authorization: Bearer {JWT}
                                      ↓
                         API Gateway Cognito Authorizer validates JWT
                                      ↓
                              Lambda receives validated claims
```

### 5.2 IAM Permissions (Least Privilege)

**Processor Lambda Role:**
- `s3:GetObject`, `s3:PutObject` on `arn:aws:s3:::bucket/*`
- `bedrock:InvokeModel` on Claude 3 Haiku and Claude 3 Sonnet ARNs only
- `ses:SendEmail`, `ses:SendRawEmail` on `*`

**Jobs Lambda Role:**
- `s3:GetObject`, `s3:ListBucket` on `arn:aws:s3:::bucket/history/*`

### 5.3 Data Protection

All S3 objects are encrypted at rest using SSE-S3. Public access is blocked at the bucket level. PDF files are accessed exclusively via pre-signed URLs with a 7-day expiry. HTML uploads and job history records are not publicly accessible.

---

## 6. Deployment Guide

### 6.1 Prerequisites

- AWS CLI configured with administrator credentials
- AWS CDK v2 installed (`npm install -g aws-cdk`)
- Docker Desktop running (required for Lambda container build)
- Python 3.11+ with `aws-cdk-lib` installed
- SES sender email verified in the target AWS region
- Bedrock Claude 3 Haiku and Sonnet models enabled in the target region

### 6.2 Deploy Steps

```bash
# 1. Bootstrap CDK (first time only)
cd email-annotator/infrastructure
cdk bootstrap

# 2. Deploy the stack
cdk deploy --parameters SesFromEmail=noreply@yourdomain.com

# 3. Note the CDK outputs
# UserPoolId: us-east-1_XXXXXXXXX
# UserPoolClientId: XXXXXXXXXXXXXXXXXXXXXXXXXX
# ApiEndpoint: https://XXXXXXXXXX.execute-api.us-east-1.amazonaws.com/prod/

# 4. Update aws-config.js with CDK output values
# frontend/src/utils/aws-config.js

# 5. Create the first user
aws cognito-idp admin-create-user \
  --user-pool-id us-east-1_XXXXXXXXX \
  --username user@yourdomain.com \
  --user-attributes Name=email,Value=user@yourdomain.com \
  --temporary-password TempPass123!

# 6. Connect GitHub repo to AWS Amplify
# AWS Console → Amplify → New App → Connect GitHub → select repo → deploy
```

---

## 7. Future Architecture (MCP Integration Roadmap)

See `mcp_opportunities_analysis.md` for the full MCP roadmap. The design is intentionally modular to accommodate these future integrations:

| Sprint | Integration Point | MCP Server | Module to Update |
|---|---|---|---|
| Sprint 1 | Link extraction | Linkinator MCP | `html_parser.py` |
| Sprint 1 | Screenshot capture | Playwright MCP | `screenshot_generator.py` |
| Sprint 1 | Review context | Bedrock Knowledge Bases MCP | `bedrock_reviewer.py` |
| Sprint 2 | Observability | CloudWatch MCP | `handler.py` |
| Sprint 2 | Job queue | SNS/SQS MCP | `handler.py` + new consumer |
| Sprint 3 | Visual review | Bedrock Data Automation MCP | `bedrock_reviewer.py` |
| Sprint 4 | CRM record | HubSpot / SFMC MCP | `handler.py` |
