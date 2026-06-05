# Implementation Plan: Re-run Annotation

## Overview

Implement the ability to re-run annotation jobs from the History page by persisting original HTML/images in S3 during initial processing, adding a re-run code path in the Processor Lambda, updating the frontend with a re-run button, and adding an S3 lifecycle rule for the `html/` prefix. Tasks are ordered so each builds on the previous, with backend changes first (persistence → re-run logic), then infrastructure, then frontend.

## Tasks

- [x] 1. Persist original HTML and images on first processing
  - [x] 1.1 Save original HTML to S3 after job completion
    - In `handler.py` `_handle_process`, capture the raw `html_content` before any image path rewriting into a variable `html_content_original`
    - After step 11 (persist job record), add a try/except block that calls `s3.put_object()` to store `html_content_original` at `html/{job_id}/original.html` with `ContentType="text/html"`
    - On failure, log a warning and continue — do not fail the pipeline
    - _Requirements: 1.1, 1.2, 1.4_

  - [x] 1.2 Copy images ZIP to persistent storage
    - When `images_s3_key` is provided, add an `s3.copy_object()` call to copy the uploaded ZIP from `uploads/{job_id}/images.zip` to `html/{job_id}/images.zip` before the `finally` cleanup block
    - Wrap in try/except — log warning on failure, do not fail the pipeline
    - _Requirements: 6.1_

  - [x] 1.3 Add `images_s3_key` and `rerun_from` fields to job record
    - Add `"images_s3_key": images_s3_key or None` and `"rerun_from": None` to the `job_record` dict in `_handle_process`
    - _Requirements: 1.3, 3.2_

  - [x] 1.4 Write property test for HTML content preservation (Property 1)
    - **Property 1: HTML content preservation (round-trip)**
    - Generate random HTML strings; mock S3 put_object; assert stored content is byte-identical to original input before rewriting
    - **Validates: Requirements 1.2**

  - [x] 1.5 Write unit tests for HTML and images persistence
    - Test HTML stored with correct S3 key and content type
    - Test images_s3_key included in job record when provided
    - Test HTML persistence failure doesn't crash pipeline
    - Test images ZIP copied to persistent location at `html/{job_id}/images.zip`
    - _Requirements: 1.1, 1.3, 1.4, 6.1_

- [x] 2. Implement re-run backend logic in Processor Lambda
  - [x] 2.1 Add re-run routing in `_handle_process`
    - At the top of `_handle_process`, check for `rerun_job_id` in the request body
    - If present and `html_content` is absent, delegate to a new `_handle_rerun(event, body, rerun_job_id)` function
    - _Requirements: 2.1_

  - [x] 2.2 Implement `_handle_rerun` function
    - Extract `user_email` from JWT claims (`requestContext.authorizer.claims.email`)
    - Extract `cognito:groups` from JWT claims to determine admin status
    - Verify ownership: call `s3.head_object()` on `history/{user_email}/{rerun_job_id}.json` — if not found and user is not admin, return HTTP 403 with `{"error": "FORBIDDEN", "message": "You do not have permission to re-run this job."}`
    - Load original HTML from `html/{rerun_job_id}/original.html` — if not found, return HTTP 404 with `{"error": "HTML_NOT_FOUND", "message": "Original HTML not available for this job. It may have been processed before this feature was enabled."}`
    - Load original job record from `history/{user_email}/{rerun_job_id}.json` (or search across users for admin) to get default `filename`, `subject_line`, `preheader_text`
    - Apply field defaulting: use request body values if non-empty, otherwise fall back to original job record values
    - Check for stored images ZIP at `html/{rerun_job_id}/images.zip` — if exists, use it; if not, proceed without images
    - Generate a new `job_id` via `str(uuid.uuid4())[:8]`
    - Set `recipient_email` from JWT claims, not from original job record
    - Run the existing pipeline logic with the loaded HTML and resolved parameters
    - After pipeline completion, persist HTML (and images if applicable) under the new `job_id`
    - Include `"rerun_from": rerun_job_id` in the new job record
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2, 6.2, 6.3_

  - [x] 2.3 Write property test for re-run field defaulting (Property 2)
    - **Property 2: Re-run field defaulting**
    - Generate random combinations of provided vs omitted fields and random original job values; assert effective value equals provided if non-empty, else original
    - **Validates: Requirements 2.2**

  - [x] 2.4 Write property test for new job_id generation (Property 3)
    - **Property 3: Re-run produces a new job_id**
    - Generate random rerun_job_id strings; assert new job_id differs from rerun_job_id
    - **Validates: Requirements 2.3**

  - [x] 2.5 Write property test for authorization/ownership enforcement (Property 4)
    - **Property 4: Authorization — ownership enforcement**
    - Generate random (email, job_id, is_admin, owns_job) tuples; mock S3 head_object; assert 403 when !admin && !owns, success when admin or owns
    - **Validates: Requirements 2.6, 2.7**

  - [ ] 2.6 Write property test for re-run traceability (Property 5)
    - **Property 5: Re-run traceability**
    - Generate random rerun_job_id strings; assert resulting job record's `rerun_from` field equals the rerun_job_id
    - **Validates: Requirements 3.2**

  - [~] 2.7 Write unit tests for re-run logic
    - Test re-run loads HTML from correct S3 key
    - Test re-run uses JWT email, not original recipient
    - Test 404 returned when HTML not in S3
    - Test 403 returned when user doesn't own job and is not admin
    - Test admin can re-run any job regardless of ownership
    - Test re-run HTML stored under new job_id
    - Test re-run uses stored images ZIP when available
    - Test re-run succeeds without images ZIP
    - _Requirements: 2.1, 2.4, 2.5, 2.6, 2.7, 3.1, 6.2, 6.3_

- [x] 3. Checkpoint
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Add S3 lifecycle rule for HTML prefix
  - [x] 4.1 Add lifecycle rule in CDK stack
    - In `infrastructure/annotator_stack.py`, add a new `s3.LifecycleRule` to the bucket definition with `id="expire-html-90-days"`, `prefix="html/"`, and `expiration=Duration.days(90)`
    - _Requirements: 5.1_

- [x] 5. Implement re-run button on History page
  - [x] 5.1 Add re-run state management to `HistoryPage` component
    - In `frontend/src/pages/HistoryPage.jsx`, add `rerunStates` and `rerunErrors` state objects using `useState`
    - Import `post` from `aws-amplify/api`
    - Implement `handleRerun(jobId)` async function that:
      - Sets the job's rerun state to `"processing"`
      - Sends POST to `/process` with `{ rerun_job_id: jobId }` and the Cognito JWT
      - On success: sets state to `"success"` and calls `loadHistory()` to refresh the list
      - On `HTML_NOT_FOUND` error: sets state to `"disabled"` and stores the error message
      - On other errors: sets state to `"error"` and stores the error message
    - Pass `onRerun`, `rerunState`, and `rerunError` props to each `JobCard`
    - _Requirements: 4.2, 4.4, 4.5, 4.6_

  - [x] 5.2 Add re-run button to `JobCard` component
    - Add a "↻ Re-run" button next to the existing PDF download link
    - Disable the button when `rerunState` is `"processing"` or `"disabled"`
    - Show "Processing…" text when state is `"processing"`
    - Display error message below the job card details when `rerunError` is set
    - Style consistently with the existing "↓ PDF" link
    - _Requirements: 4.1, 4.3, 4.5, 4.6_

  - [~] 5.3 Write unit tests for re-run UI behavior
    - Test re-run button renders on each job card
    - Test re-run button sends correct POST payload with `rerun_job_id`
    - Test button disabled during processing
    - Test job list refreshes after successful re-run
    - Test error scoped to affected card only
    - Test HTML_NOT_FOUND disables button permanently
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [ ] 6. Final checkpoint
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- The backend uses Python 3.11 (Lambda Docker); the frontend uses React 18 with Vite
- Property tests use Hypothesis (already in project dependencies)
- All property and unit tests mock AWS services (S3, Bedrock, SES) — no external calls
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
