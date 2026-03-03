# Hook: pre-commit

**Trigger:** Before every git commit
**Type:** Blocking (commit is aborted if this hook fails)

## Purpose

This hook runs automated quality checks before any code is committed to the repository. It ensures that no broken code, hardcoded secrets, or missing tests are introduced into the codebase.

## Steps

### Step 1 — Python Linting and Type Checking

Run `ruff` on all Python files in `backend/` to catch syntax errors, unused imports, and style violations. Run `mypy` on `handler.py`, `bedrock_reviewer.py`, and `bedrock_classifier.py` to catch type errors.

```bash
ruff check backend/
mypy backend/docker/handler.py backend/docker/bedrock_reviewer.py backend/docker/bedrock_classifier.py
```

**On failure:** Abort commit and display the specific linting errors with file and line numbers.

### Step 2 — Secret Scanning

Scan all staged files for hardcoded AWS credentials, API keys, or sensitive strings using `detect-secrets` or `truffleHog`.

```bash
detect-secrets scan --baseline .secrets.baseline
```

**Patterns to flag:**
- `AKIA[0-9A-Z]{16}` (AWS Access Key ID)
- `aws_secret_access_key\s*=\s*[^\s]+`
- Any string matching `sk-[a-zA-Z0-9]{32,}`
- Hardcoded email addresses in non-test code
- Hardcoded S3 bucket names (should be env vars)

**On failure:** Abort commit, display the matched pattern and file location, and instruct the developer to move the value to an environment variable or AWS Secrets Manager.

### Step 3 — Unit Test Execution

Run the Python unit test suite for the backend modules.

```bash
cd backend && python -m pytest tests/ -v --tb=short
```

**On failure:** Abort commit and display the failing test names and assertion errors.

### Step 4 — CDK Synth Validation

Run `cdk synth` to validate that the infrastructure code is syntactically correct and produces a valid CloudFormation template.

```bash
cd infrastructure && cdk synth --quiet
```

**On failure:** Abort commit and display the CDK synthesis error.

### Step 5 — Frontend Build Check

Run `npm run build` in the `frontend/` directory to ensure the React application compiles without errors.

```bash
cd frontend && npm run build
```

**On failure:** Abort commit and display the Vite build error.

## Agent Instructions

When assisting with code changes, always run the equivalent of these checks before suggesting a commit. If any check fails, diagnose the root cause and propose a fix before proceeding. Never suggest bypassing these checks with `--no-verify`.
