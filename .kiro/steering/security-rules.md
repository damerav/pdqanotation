# Agent Steering: Security Rules

**Project:** Email Campaign Annotator
**Applies to:** All files in all layers (frontend, backend, infrastructure)

---

## Overview

This project handles HTML email content that may contain proprietary pharmaceutical marketing copy, client brand assets, and personally identifiable information (user email addresses). The following security rules are non-negotiable and must be applied to every code change without exception.

---

## Authentication and Authorization

**Rule SEC-1: No unauthenticated API access.** Every API Gateway route except `OPTIONS` (CORS preflight) must have the Cognito JWT authorizer attached. When adding a new API route in `annotator_stack.py`, always include `**auth_opts` in the `add_method()` call.

```python
# Correct — always include auth_opts
process_res.add_method("POST", apigw.LambdaIntegration(processor_fn), **auth_opts)

# Wrong — never do this
process_res.add_method("POST", apigw.LambdaIntegration(processor_fn))
```

**Rule SEC-2: No self-registration.** The Cognito User Pool must always have `self_sign_up_enabled=False`. Never change this setting. Users are added exclusively by administrators via the AWS CLI.

**Rule SEC-3: User data isolation.** Job history records are stored under `history/{user_email}/`. The Jobs Lambda extracts the user's email from the Cognito JWT claims (`requestContext.authorizer.claims.email`), not from a query parameter. Never trust user-supplied email addresses for data access paths.

---

## Secrets and Credentials

**Rule SEC-4: No hardcoded credentials.** AWS credentials, API keys, bucket names, and email addresses must never appear in source code. All configuration is passed via Lambda environment variables set in `annotator_stack.py`. The pre-commit hook scans for credential patterns — do not attempt to bypass it.

**Rule SEC-5: No credentials in frontend code.** The `aws-config.js` file contains only public Cognito configuration values (User Pool ID, Client ID, API endpoint). These are not secrets. Never put AWS access keys, secret keys, or SES credentials in any frontend file.

**Rule SEC-6: Environment variables in Lambda.** All Lambda environment variables are set in the CDK stack. When a new configuration value is needed, add it as a Lambda environment variable in `annotator_stack.py` and read it with `os.environ.get("VAR_NAME")` in the Python code. Never use AWS Secrets Manager for values that are not genuinely secret (bucket names, region names are not secrets).

---

## S3 Data Protection

**Rule SEC-7: Public access blocked.** The S3 bucket must always have `block_public_access=s3.BlockPublicAccess.BLOCK_ALL`. Never add a bucket policy that grants public read access.

**Rule SEC-8: Pre-signed URLs only.** PDF files are accessed exclusively via pre-signed S3 URLs with a 7-day expiry (`ExpiresIn=604800`). Never generate a public URL for any S3 object. Never set an S3 object's ACL to `public-read`.

**Rule SEC-9: Encryption at rest.** The S3 bucket uses SSE-S3 encryption (`encryption=s3.BucketEncryption.S3_MANAGED`). Do not change this to unencrypted storage.

**Rule SEC-10: Lifecycle policy.** The `pdfs/` prefix has a 7-day lifecycle expiry policy. This limits the window of exposure for generated PDFs. Do not increase this expiry without a documented business justification.

---

## Input Validation

**Rule SEC-11: HTML file size limit.** The processor Lambda must reject HTML files larger than 5 MB (`len(html_content) > 5_000_000`). This prevents memory exhaustion and excessively long Bedrock calls.

**Rule SEC-12: Content type validation.** The frontend must validate that the uploaded file has a `.html` extension before sending it to the API. The Lambda must also verify that the `html_content` field begins with a valid HTML tag (`<html`, `<!DOCTYPE`, `<head`, `<body`).

**Rule SEC-13: No server-side rendering of user HTML.** The HTML email content is passed to Playwright's `page.set_content()` in a sandboxed Chromium instance. It is never rendered in the Lambda's own process or returned to the browser. This prevents XSS via malicious HTML in the uploaded file.

---

## IAM Least Privilege

**Rule SEC-14: Specific resource ARNs.** All IAM policy statements must use specific resource ARNs, not wildcards. The only exception is `ses:SendEmail` which requires `"*"` due to SES API constraints.

**Rule SEC-15: Separate roles per function.** The Processor Lambda and the Jobs Lambda have separate IAM roles. The Jobs Lambda has read-only S3 access (`s3:GetObject`, `s3:ListBucket`) and no Bedrock or SES permissions.

**Rule SEC-16: No `AdministratorAccess`.** Never attach `AdministratorAccess` or `PowerUserAccess` managed policies to any Lambda role. Always define explicit inline policies.

---

## Network Security

**Rule SEC-17: HTTPS only.** All communication between the browser and API Gateway uses HTTPS. API Gateway enforces TLS 1.2 minimum by default. Do not add HTTP endpoints.

**Rule SEC-18: CORS restriction (production).** The current CORS configuration allows all origins (`*`) for development convenience. Before production go-live, restrict `allow_origins` in the CDK stack to the specific Amplify CloudFront domain.

```python
# Development (current)
allow_origins=apigw.Cors.ALL_ORIGINS

# Production (required before go-live)
allow_origins=["https://main.XXXXXXXXXX.amplifyapp.com"]
```

---

## Incident Response

If a security issue is discovered (e.g., a pre-signed URL is shared externally, an S3 bucket is misconfigured, or credentials are accidentally committed), take the following steps in order:

1. Immediately revoke the affected credential or pre-signed URL by deleting the S3 object.
2. Run `git filter-branch` or `git-secrets --scan-history` to remove any committed secrets from git history.
3. Rotate the affected AWS credentials in the IAM console.
4. Review CloudTrail logs for the affected time period to assess the scope of any unauthorised access.
5. Update the `.secrets.baseline` file and re-run the pre-commit secret scan.
