# Agent Steering: Project Context

**Project:** Email Campaign Annotator
**Version:** 1.0
**Author:** Vamshi Damera

---

## Project Identity

This project automates the creation of annotated PDF proofs for HTML email campaigns at a pharmaceutical marketing agency. The system replaces a 13-minute manual workflow involving Outlook, Dreamweaver, Email on Acid, and Adobe InDesign with a fully automated AWS cloud pipeline that delivers results to the user's inbox in under 5 minutes.

The target users are 5–10 email marketing professionals. They are not engineers. The web application must be simple, reliable, and require no technical knowledge to operate.

---

## Technology Stack

When working on this project, always operate within the following technology boundaries. Do not introduce new frameworks, languages, or services without first consulting `.kiro/hooks/on-new-feature.md`.

| Layer | Technology | Notes |
|---|---|---|
| Frontend | React 18, Vite, AWS Amplify UI | No Redux; useState only |
| Auth | Amazon Cognito | Email + password; no self-registration |
| API | Amazon API Gateway (REST) | Cognito JWT authorizer on all routes |
| Processing | AWS Lambda (Docker, Python 3.11) | 3 GB memory, 5 min timeout |
| AI — Classification | AWS Bedrock, Claude 3 Haiku | Fast, cheap link labelling |
| AI — Review | AWS Bedrock, Claude 3 Sonnet | Deep quality analysis |
| Screenshots | Playwright + Chromium (in Lambda) | Desktop 1200px, Mobile 390px |
| PDF | ReportLab | 3-page: review + desktop + mobile |
| Storage | Amazon S3 | Single bucket, 3 prefixes |
| Email delivery | Amazon SES | HTML email with PDF link |
| Hosting | AWS Amplify | Auto-deploy from GitHub |
| IaC | AWS CDK v2 (Python) | Single stack: `EmailAnnotatorStack` |

---

## Coding Standards

### Python (backend)

All Python code in `backend/` must follow these standards. When generating or reviewing Python code, apply these rules without being asked.

The code style follows PEP 8 with a maximum line length of 100 characters. All functions must have type hints on parameters and return values. All public functions must have a one-line docstring. Error handling must use specific exception types, not bare `except:` clauses. Environment variables must be read at module level using `os.environ.get()` with a sensible default where applicable. AWS clients (`boto3`) must be instantiated at module level, not inside functions, to benefit from Lambda's execution context reuse.

```python
# Correct pattern for AWS client instantiation
import boto3
bedrock = boto3.client("bedrock-runtime")  # module level ✓

def classify_links(raw_links: list[dict]) -> list[dict]:
    """Classify email links using Claude 3 Haiku via Bedrock."""
    ...
```

### JavaScript/React (frontend)

All React components must be functional components using hooks. No class components. Props must be destructured in the function signature. Event handlers must be named with the `handle` prefix (e.g., `handleSubmit`, `handleFileChange`). API calls must always include a loading state and an error state. The Cognito JWT must always be obtained via `fetchAuthSession()` from `aws-amplify/auth`; never store it in `localStorage` or `sessionStorage`.

### Infrastructure (CDK)

All CDK constructs must use the `self` prefix for resource naming to avoid naming conflicts across stacks. All Lambda environment variables must be passed through the CDK stack, never hardcoded in the Lambda code. All IAM policy statements must include a `sid` (statement ID) for auditability. Resource removal policies must be set to `RETAIN` for S3 buckets in production to prevent accidental data loss.

---

## Architecture Principles

The following principles govern all architectural decisions in this project. When evaluating a proposed change, check it against these principles first.

**Serverless first.** All compute must use AWS Lambda or AWS Amplify. Do not introduce EC2 instances, ECS tasks, or always-on servers. The system must scale to zero when idle.

**Single responsibility.** Each Python module in `backend/docker/` handles exactly one pipeline stage. The orchestrator (`handler.py`) calls each module in sequence but contains no business logic itself. If a module grows beyond 150 lines, split it.

**Bedrock for intelligence, not rules.** Do not hardcode link classification rules or quality check rules in Python. These decisions belong to the LLM. Python code handles data extraction, validation, and formatting only.

**Graceful degradation.** Every Bedrock call must have a fallback. If the AI is unavailable, the pipeline must still produce a PDF (without AI-generated content) and notify the user. Never fail silently.

**Least privilege.** Every Lambda function's IAM role must grant only the minimum permissions required. When in doubt, check the CDK stack's IAM policy statements before adding new permissions.

---

## File Organisation

When creating new files, place them in the correct location according to this structure:

```
email-annotator/
├── .kiro/                    ← Kiro specs, hooks, steering, skills
│   ├── specs/                ← requirements.md, design.md
│   ├── hooks/                ← pre-commit, post-deploy, on-change hooks
│   ├── steering/             ← project context, bedrock, security rules
│   └── skills/               ← reusable agent skill definitions
├── frontend/
│   └── src/
│       ├── pages/            ← UploadPage.jsx, HistoryPage.jsx
│       ├── components/       ← Reusable UI components
│       └── utils/            ← aws-config.js, api.js helpers
├── backend/
│   ├── docker/               ← Lambda container: handler + all pipeline modules
│   │   ├── handler.py        ← Orchestrator (calls all modules)
│   │   ├── html_parser.py    ← Link + metadata extraction
│   │   ├── bedrock_classifier.py  ← Claude 3 Haiku link classification
│   │   ├── bedrock_reviewer.py    ← Claude 3 Sonnet quality review
│   │   ├── screenshot_generator.py ← Playwright screenshots
│   │   ├── image_annotator.py     ← Pillow callout overlay
│   │   └── pdf_builder.py         ← ReportLab PDF assembly
│   └── lambda/               ← Lightweight ZIP Lambdas (jobs history)
│       └── jobs_handler.py
├── infrastructure/
│   ├── annotator_stack.py    ← CDK stack (all AWS resources)
│   └── app.py                ← CDK app entry point
└── tests/
    ├── unit/                 ← Unit tests per module
    └── integration/          ← Integration tests with mocked AWS
```

---

## Naming Conventions

| Entity | Convention | Example |
|---|---|---|
| Python files | `snake_case.py` | `bedrock_reviewer.py` |
| Python functions | `snake_case` | `classify_links()` |
| Python constants | `UPPER_SNAKE_CASE` | `REVIEW_MODEL` |
| React components | `PascalCase.jsx` | `UploadPage.jsx` |
| React functions | `camelCase` | `handleSubmit` |
| CDK constructs | `PascalCase` | `ProcessorFn`, `EmailAnnotatorBucket` |
| S3 prefixes | `kebab-case/` | `pdfs/`, `history/` |
| Job IDs | 8-char hex UUID | `a1b2c3d4` |
| Environment variables | `UPPER_SNAKE_CASE` | `SES_FROM_EMAIL`, `S3_BUCKET` |
