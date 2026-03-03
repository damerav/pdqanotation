# Kiro Task: Generate All Project Documentation

**Task ID:** generate-docs
**Version:** 1.0
**Author:** Vamshi Damera
**Last updated:** March 03, 2026

---

## How to Use This Prompt

Copy everything inside the code block below and paste it directly into the Kiro agent chat.
The agent will read the codebase and generate all project documentation from scratch.

---

## Prompt

```
You are a senior technical writer and solutions architect working on the Email Campaign
Annotator project — an AWS-native web application that automates the creation of annotated
PDF proofs for HTML email campaigns.

Your task is to read the entire codebase and generate a complete, production-quality
documentation suite. Do not use placeholder text or stub sections. Every document must
be fully written based on what you actually find in the code.

---

STEP 1: READ THE CODEBASE

Read the following files in this exact order before writing anything. Extract the real
implementation details — function signatures, API contracts, AWS resource names, error
codes, environment variables, and business logic — and use them as the source of truth
for all documentation.

  .kiro/steering/project-context.md       ← tech stack, coding standards, conventions
  .kiro/steering/bedrock-rules.md         ← Bedrock model IDs, prompt patterns, cost rules
  .kiro/steering/security-rules.md        ← security requirements (SEC-1 through SEC-18)
  .kiro/specs/requirements.md             ← functional and non-functional requirements
  .kiro/specs/design.md                   ← architecture, data models, component design
  .kiro/skills/bedrock-prompt-engineering.md  ← Bedrock prompt templates and review criteria
  .kiro/skills/mcp-integration.md         ← MCP roadmap (8 servers across 4 sprints)
  .kiro/skills/pdf-generation.md          ← PDF structure, page layout, callout design
  .kiro/skills/aws-cdk-infrastructure.md  ← CDK patterns, IAM policies, deployment commands
  backend/docker/handler.py               ← pipeline orchestration, error handling, job record
  backend/docker/html_parser.py           ← link extraction, metadata, deduplication
  backend/docker/bedrock_classifier.py    ← Claude 3 Haiku classification, JSON schema
  backend/docker/bedrock_reviewer.py      ← Claude 3 Sonnet review, 6 categories, scoring
  backend/docker/screenshot_generator.py ← Playwright viewports, wait conditions
  backend/docker/image_annotator.py       ← Pillow callout badges, positioning logic
  backend/docker/pdf_builder.py           ← ReportLab 3-page PDF, fallback handling
  backend/lambda/jobs_handler.py          ← GET /jobs, pagination, S3 history read
  infrastructure/annotator_stack.py       ← all AWS resources, IAM roles, CDK outputs
  frontend/src/App.jsx                    ← Amplify Authenticator, routing
  frontend/src/pages/UploadPage.jsx       ← upload form, job status, review score display
  frontend/src/pages/HistoryPage.jsx      ← history list, download links, score badges
  frontend/src/utils/aws-config.js        ← Cognito config keys, API endpoint

After reading all files, confirm: "I have read all source files. Beginning documentation
generation." Then proceed to Step 2.

---

STEP 2: GENERATE EACH DOCUMENT

Generate the following 9 documents in order. Write each one in full before moving to the
next. Save each file to the exact path shown. Do not skip sections or use placeholder text.

---

DOCUMENT 1: docs/user-guide.md

Write a complete end-user guide for non-technical email marketing professionals.
Cover: what the tool does and why it replaces the manual process; how to log in (Cognito,
admin-created accounts only, no self-registration); file requirements (HTML only, 5 MB max,
UTF-8); the upload form fields (file, subject line, recipient email); what happens after
submission (job status card, quality score, issue counts); how to read the 3-page PDF
(Page 1 review report with score and issues table, Page 2 annotated desktop screenshot
with callout legend, Page 3 annotated mobile screenshot); the History page and 7-day PDF
expiry; a FAQ section answering at least 8 common questions; and a troubleshooting table
covering the most common errors with causes and fixes.

Use plain language. Avoid AWS jargon. Write for someone who has never used the tool before.

---

DOCUMENT 2: docs/developer-guide.md

Write a complete developer reference guide. Cover: the full architecture diagram in ASCII
or Mermaid showing all 5 AWS services and how they connect; local development prerequisites
(Python 3.11, Node 18, Docker, AWS CLI v2, CDK v2) with exact install commands; step-by-step
local setup (clone, configure AWS credentials, set env vars, install backend deps, install
Playwright browsers, install frontend deps, configure aws-config.js, run dev server);
the complete project directory structure with a comment explaining every file's purpose;
a module reference for each of the 7 backend Python modules (purpose, inputs, outputs,
key functions, error handling); the frontend authentication flow (Amplify Authenticator,
fetchAuthSession, JWT in Authorization header); the CDK stack resources; the three-tier
testing strategy (unit, integration, smoke); how to add a new feature (reference
.kiro/hooks/on-new-feature.md); the Kiro specification system and how to use it; the
full deployment guide (first deploy and subsequent deploys); and a complete environment
variables reference table.

---

DOCUMENT 3: docs/api-reference.md

Write a complete REST API reference. Base URL format, authentication (Cognito JWT Bearer
token, token expiry, refresh pattern). For POST /process: full request spec (multipart
fields, types, required/optional, size limits), a curl example, the complete 200 OK
response JSON with every field documented (job_id, status, file_name, timestamps,
duration_seconds, pdf_url, pdf_expires_at, review object with score/summary/issue_counts,
links object with total counts), and all error responses (400 MISSING_FILE,
400 INVALID_FILE_TYPE, 400 FILE_TOO_LARGE, 400 INVALID_HTML, 401, 500 PROCESSING_ERROR)
with example error response bodies. For GET /jobs: query parameters (limit, after),
curl example, complete 200 OK response with the jobs array (all fields including
pdf_available boolean), pagination fields (count, has_more), and error responses.
Rate limits table. Data retention policy (7-day PDF lifecycle, indefinite job history).
CORS configuration and the production hardening note.

---

DOCUMENT 4: docs/operations-runbook.md

Write a complete operations runbook for an administrator with AWS console access.
Cover: system overview table (all 6 AWS services, purpose, console link, estimated
monthly cost); routine operations with exact AWS CLI commands for adding a user,
disabling a user, listing all users, verifying a new SES recipient, and requesting
SES production access; monitoring section with a table of 8 key CloudWatch metrics
(metric name, namespace, alarm threshold, action), CloudWatch Logs commands to tail
Lambda logs and search by job ID, and a CloudWatch alarm creation command; 5 incident
response playbooks (INC-001 job processing failure with common error table and fixes,
INC-002 users cannot log in with investigation and fix commands, INC-003 frontend not
loading with Amplify deployment commands, INC-004 PDF download 403 with explanation
and user guidance, INC-005 Bedrock review score missing with investigation and fix);
backup and recovery (S3 versioning, file recovery commands, infrastructure recovery);
cost management (monthly cost estimate table for 100 campaigns, billing alert command);
security operations (IAM review commands, S3 public access check, Cognito auth event
review); and a monthly health check checklist with all commands.

---

DOCUMENT 5: docs/adr/ADR-001-aws-amplify-hosting.md

Write an Architecture Decision Record for the choice of AWS Amplify for frontend hosting.
Use the standard ADR format: Status, Date, Author, Deciders, Context (what problem was
being solved, what alternatives were considered: S3+CloudFront manual, Lightsail, ECS),
Decision (what was chosen and why), Rationale (specific technical reasons: managed CI/CD
from GitHub, Amplify UI Authenticator component, amplify.yml declarative builds, automatic
HTTPS and CDN, small team with no DevOps resource), and Consequences (positive: zero server
management, automatic deploys, native Cognito integration; negative: limited CloudFront
customisation; cost: under $1/month for internal tool).

---

DOCUMENT 6: docs/adr/ADR-002-bedrock-model-selection.md

Write an Architecture Decision Record for the two-model Bedrock strategy. Context: two
distinct AI tasks with different requirements (fast structured classification vs. deep
reasoning review). Decision: Claude 3 Haiku for link classification, Claude 3 Sonnet for
quality review. Rationale: Haiku is fastest/cheapest Claude 3 model, ideal for structured
JSON extraction tasks, < $0.001 per email for classification; Sonnet provides significantly
better reasoning for multi-criteria evaluation, cost justified by review quality improvement;
AWS Bedrock chosen over direct Anthropic API for data residency, IAM access control, no
API keys to manage, consistent Lambda latency. Consequences: positive (cost-optimised,
all data within AWS, IAM-controlled); negative (Bedrock model availability varies by region,
both models must be enabled in console); future consideration (Claude 3.5 Sonnet upgrade
path, prompt is model-agnostic).

---

DOCUMENT 7: docs/adr/ADR-003-single-lambda-architecture.md

Write an Architecture Decision Record for the single Lambda container architecture.
Context: 6-stage sequential pipeline, low volume (< 100 campaigns/month), small team,
no dedicated DevOps. Alternatives: Step Functions (one Lambda per stage), ECS Fargate task,
single Lambda ZIP (rejected — Playwright exceeds 250 MB ZIP limit). Decision: single Lambda
Docker container (10 GB image limit, 3 GB memory, 5-minute timeout). Rationale: eliminates
state machine definition, inter-stage S3/SQS data passing, per-stage IAM roles, and
distributed debugging complexity; all stages share in-memory state naturally; Docker
required for Playwright + Chromium (~500 MB); per-stage fallbacks implemented within
single function. Consequences: positive (simple deployment, easy local testing, natural
state sharing, straightforward CloudWatch logging); negative (all stages share timeout
budget; if P95 > 4 minutes, investigate); migration path to Step Functions documented
in .kiro/skills/mcp-integration.md Sprint 4.

---

DOCUMENT 8: docs/adr/ADR-004-mcp-integration-roadmap.md

Write an Architecture Decision Record for the phased MCP server integration roadmap.
Context: several pipeline capabilities have well-maintained MCP server equivalents
(Linkinator for URL validation, Playwright MCP for screenshots, Bedrock Knowledge Bases
for brand-aware review). Decision: ship initial version with custom implementations,
migrate to MCP servers in 4 planned sprints. Rationale: avoids delaying launch; validates
core pipeline with real users before MCP investment; each sprint delivers measurable value.
Sprint 1 (highest priority): Linkinator MCP for live URL reachability, Playwright MCP to
remove Chromium from container, Bedrock Knowledge Bases MCP for RAG-based brand guidelines.
Sprint 2: CloudWatch MCP for metrics, SNS/SQS MCP to eliminate API Gateway timeout.
Sprint 3: Bedrock Data Automation MCP for visual review of rendered screenshots.
Sprint 4: HubSpot/SFMC MCP for CRM integration, Step Functions MCP for orchestration.
Consequences: known limitations in initial version (no live URL checking, no brand-aware
review); decision criteria for Sprint 1 start (20 real campaigns processed, user feedback
collected).

---

DOCUMENT 9: tests/scripts/validate_connections.py

Write a complete Python script that validates all AWS service connections required by
the pipeline. The script must:

- Check 8 services: AWS credentials (STS get-caller-identity), S3 bucket (head_bucket +
  verify public access is fully blocked — fail with SEC-7 violation message if not),
  Cognito User Pool (describe_user_pool + verify AllowAdminCreateUserOnly=true — fail with
  SEC-2 violation message if self-signup is enabled), Bedrock Claude 3 Haiku (invoke_model
  with max_tokens=10), Bedrock Claude 3 Sonnet (invoke_model with max_tokens=10),
  SES sender email (get_identity_verification_attributes + check sandbox mode),
  API Gateway (get_rest_api + verify /process and /jobs routes exist),
  Amplify app (get_app + list_branches + check latest deployment status).

- Read configuration from environment variables: S3_BUCKET, COGNITO_USER_POOL_ID,
  SES_FROM_EMAIL, API_GATEWAY_ID, AMPLIFY_APP_ID, AWS_DEFAULT_REGION.

- For each check: measure duration in milliseconds, return a CheckResult dataclass with
  name, passed (bool), message, fix (specific AWS CLI command to resolve the failure),
  duration_ms, and details dict.

- Print a colour-coded human-readable report (green ✓ PASS, red ✗ FAIL) with all fix
  commands grouped at the end, and an OVERALL STATUS line.

- Support a --json flag for machine-readable output (for CI/CD integration).

- Support a --region flag defaulting to AWS_DEFAULT_REGION or us-east-1.

- Exit with code 0 if all checks pass, code 1 if any fail.

Use boto3. Handle NoCredentialsError, ClientError, and generic exceptions separately
with specific fix messages for each. Do not use any external dependencies beyond boto3
and the Python standard library.

---

STEP 3: VERIFY COMPLETENESS

After generating all 9 documents, verify:

  1. All 9 files exist at their correct paths
  2. No document contains placeholder text like "[TODO]", "[INSERT]", or "..."
  3. Every AWS CLI command in the runbook uses real parameter names
  4. Every code example in the developer guide is syntactically correct Python or JavaScript
  5. The API reference response schemas match the actual fields returned by handler.py
  6. The validate_connections.py script is complete and runnable (no stub functions)

Report the verification result in this format:

  DOCUMENTATION GENERATION COMPLETE
  ──────────────────────────────────
  docs/user-guide.md              ✓  (<word count> words)
  docs/developer-guide.md         ✓  (<word count> words)
  docs/api-reference.md           ✓  (<word count> words)
  docs/operations-runbook.md      ✓  (<word count> words)
  docs/adr/ADR-001-*.md           ✓  (<word count> words)
  docs/adr/ADR-002-*.md           ✓  (<word count> words)
  docs/adr/ADR-003-*.md           ✓  (<word count> words)
  docs/adr/ADR-004-*.md           ✓  (<word count> words)
  tests/scripts/validate_connections.py  ✓  (<line count> lines)

  STATUS: All documents generated. Commit with: git add docs/ tests/scripts/ && git commit -m "docs: generate full documentation suite via Kiro"
```
