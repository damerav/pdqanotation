# Hook: on-backend-change

**Trigger:** When any file in `backend/docker/` is saved or modified
**Type:** Advisory (runs automatically; surfaces suggestions without blocking)

## Purpose

This hook provides immediate feedback when backend pipeline modules are edited. It checks for common issues specific to each module and reminds the developer of downstream impacts.

## Module-Specific Rules

### When `bedrock_classifier.py` is modified

1. **Verify model ID constant** — Ensure `MODEL_ID` is set to `anthropic.claude-3-haiku-20240307-v1:0`. Do not change to a more expensive model without updating the cost estimate in `README.md`.

2. **Check system prompt integrity** — The system prompt must instruct the model to return `{"links": [...]}` JSON only. If the prompt is changed, run the integration test `tests/test_classifier.py` to verify the output schema is still valid.

3. **Verify fallback logic** — The `except` block must always return a list of the same length as `raw_links`. If it returns a shorter list, the letter assignment in `handler.py` will be misaligned.

4. **Remind:** Any change to the link schema (adding/removing fields) must be reflected in `image_annotator.py` and `pdf_builder.py`.

### When `bedrock_reviewer.py` is modified

1. **Verify model ID constant** — Ensure `REVIEW_MODEL` is set to `anthropic.claude-3-sonnet-20240229-v1:0`.

2. **Check JSON schema in system prompt** — The system prompt defines the expected JSON structure. If the schema changes, update `_validate_report()` to handle the new fields and update the PDF builder's review page renderer.

3. **Check temperature setting** — Temperature must remain at `0.1` for consistent structured output. Higher values increase the risk of malformed JSON responses.

4. **Verify `_validate_report()` covers all new fields** — Every new field added to the schema must have a safe default in `_validate_report()`.

5. **Check HTML truncation limit** — The HTML sample sent to the model is limited to 8,000 characters. If this limit is changed, verify that the Lambda's 5-minute timeout is still sufficient.

### When `screenshot_generator.py` is modified

1. **Verify viewport dimensions** — Desktop must be 1200×900; mobile must be 390×844. These match the dimensions expected by `image_annotator.py` for callout positioning.

2. **Check `networkidle` wait** — The `wait_until="networkidle"` parameter must be preserved. Removing it may cause screenshots to be captured before images are loaded.

3. **Memory warning** — Playwright with Chromium uses approximately 800 MB of the Lambda's 3,008 MB allocation. Do not add additional browser contexts without increasing Lambda memory.

### When `pdf_builder.py` is modified

1. **Verify page order** — Pages must be in order: Review Report (Page 1), Desktop View (Page 2), Mobile View (Page 3). Changing this order breaks the client's established review workflow.

2. **Check colour constants** — Score colours must match the SES email: green `#166534` for ≥ 80, amber `#92400e` for ≥ 60, red `#991b1b` for < 60.

3. **Verify fallback for missing review** — If `review` is `None` or `overall_score` is `None`, Page 1 must still render gracefully without throwing an exception.

### When `handler.py` is modified

1. **Check pipeline step order** — The 10-step pipeline sequence must not be reordered. Steps 3 (classify) and 4 (review) are independent and could theoretically run in parallel, but sequential execution is required for simplicity in v1.

2. **Verify error response format** — All error responses must use `_resp(500, {"error": str(e)})`. Do not expose internal stack traces in the response body.

3. **Check CORS headers** — The `_resp()` helper must include `Access-Control-Allow-Origin: *` on all responses.

4. **Verify S3 pre-signed URL expiry** — The pre-signed URL must use `ExpiresIn=604800` (7 days). This matches the S3 lifecycle policy on the `pdfs/` prefix.

## Agent Instructions

When editing any backend module, apply these rules proactively. If a rule is violated, flag it immediately with the specific line number and the correct value. Do not wait for a test failure to surface these issues.
