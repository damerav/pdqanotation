# Requirements Document

## Introduction

The Email Campaign Annotator currently discards the original HTML content after processing a job. Users who want to re-annotate a campaign (e.g., after a pipeline bugfix is deployed) must re-upload the HTML file through the Upload page. This feature adds the ability to re-run annotation directly from the History page by persisting the original HTML in S3 and providing a one-click re-run action on each job card.

## Glossary

- **Pipeline**: The full annotation processing sequence in `handler.py` — parse links, classify with Bedrock, review with Bedrock, capture screenshots, annotate images, build PDF, send email via SES.
- **Job_Record**: A JSON object stored at `history/{user_email}/{job_id}.json` in S3 that captures metadata about a completed annotation job.
- **Original_HTML**: The raw HTML email content submitted by the user during the initial upload, before any image path rewriting or processing.
- **Processor_Lambda**: The Docker-based Lambda function (`handler.py`) that orchestrates the annotation pipeline.
- **History_Page**: The React page (`HistoryPage.jsx`) that displays past annotation jobs as cards with score, summary, and PDF download link.
- **Job_Card**: A single UI element on the History_Page representing one completed annotation job.
- **Re-run**: The act of re-processing a previously completed job using the stored Original_HTML and the latest Pipeline code, producing a new annotated PDF.

## Requirements

### Requirement 1: Persist Original HTML on First Processing

**User Story:** As a user, I want the system to save my uploaded HTML when I first process a campaign, so that I can re-annotate it later without re-uploading the file.

#### Acceptance Criteria

1. WHEN the Processor_Lambda successfully completes a job, THE Processor_Lambda SHALL store the Original_HTML in S3 at the key `html/{job_id}/original.html` with content type `text/html`.
2. WHEN the Processor_Lambda stores the Original_HTML, THE Processor_Lambda SHALL store the unmodified HTML content as received in the request body, before any image path rewriting.
3. WHEN the Processor_Lambda stores the Original_HTML, THE Processor_Lambda SHALL also store the `images_s3_key` value (if provided) in the Job_Record so the images ZIP reference is preserved for re-runs.
4. IF the S3 put operation for the Original_HTML fails, THEN THE Processor_Lambda SHALL log the error and continue the pipeline without failing the job, since HTML persistence is a non-critical enhancement.

### Requirement 2: Re-run API Endpoint

**User Story:** As a user, I want the system to accept a re-run request using a previously stored campaign, so that I can re-process it with the latest pipeline code.

#### Acceptance Criteria

1. WHEN the Processor_Lambda receives a POST request to `/process` with a `rerun_job_id` field and no `html_content` field, THE Processor_Lambda SHALL treat the request as a re-run by loading the Original_HTML from S3 at `html/{rerun_job_id}/original.html`.
2. WHEN the Processor_Lambda processes a re-run request, THE Processor_Lambda SHALL use the `filename`, `subject_line`, and `preheader_text` from the original Job_Record if those fields are not provided in the re-run request body.
3. WHEN the Processor_Lambda processes a re-run request, THE Processor_Lambda SHALL generate a new unique `job_id` for the re-run result so the original job record is preserved.
4. WHEN the Processor_Lambda processes a re-run request, THE Processor_Lambda SHALL use the `recipient_email` from the authenticated user's JWT claims, not from the original Job_Record.
5. IF the Original_HTML for the specified `rerun_job_id` does not exist in S3, THEN THE Processor_Lambda SHALL return HTTP 404 with error code `HTML_NOT_FOUND` and message "Original HTML not available for this job. It may have been processed before this feature was enabled."
6. WHEN the Processor_Lambda processes a re-run request, THE Processor_Lambda SHALL verify that the authenticated user owns the original Job_Record by checking that `history/{user_email}/{rerun_job_id}.json` exists, unless the user is in the `admin` Cognito group.
7. IF the authenticated user does not own the original Job_Record and is not an admin, THEN THE Processor_Lambda SHALL return HTTP 403 with error code `FORBIDDEN` and message "You do not have permission to re-run this job."

### Requirement 3: Persist Original HTML for Re-run Jobs

**User Story:** As a user, I want re-run jobs to also store their HTML, so that I can re-run a re-run in the future.

#### Acceptance Criteria

1. WHEN the Processor_Lambda completes a re-run job, THE Processor_Lambda SHALL store the Original_HTML under the new job's key `html/{new_job_id}/original.html` so the new job is independently re-runnable.
2. WHEN the Processor_Lambda creates a Job_Record for a re-run, THE Processor_Lambda SHALL include a `rerun_from` field containing the original `rerun_job_id` to maintain traceability.

### Requirement 4: Re-run Button on History Page Job Cards

**User Story:** As a user, I want a re-run button on each job card in the History page, so that I can trigger reprocessing with one click.

#### Acceptance Criteria

1. THE History_Page SHALL display a "Re-run" button on each Job_Card next to the existing PDF download link.
2. WHEN the user clicks the Re-run button, THE History_Page SHALL send a POST request to `/process` with the `rerun_job_id` set to the job's `job_id`.
3. WHILE a re-run request is in progress for a Job_Card, THE History_Page SHALL disable the Re-run button for that card and display a "Processing…" indicator.
4. WHEN a re-run request completes successfully, THE History_Page SHALL refresh the job list to show the new job at the top.
5. IF a re-run request fails, THEN THE History_Page SHALL display the error message on the affected Job_Card without disrupting other cards.
6. WHEN a re-run request fails with error code `HTML_NOT_FOUND`, THE History_Page SHALL display the message "Original HTML not available for this job" and disable the Re-run button for that card.

### Requirement 5: S3 Lifecycle Policy for Stored HTML

**User Story:** As an administrator, I want stored HTML files to have a defined retention period, so that storage costs remain predictable.

#### Acceptance Criteria

1. THE CDK stack SHALL define an S3 lifecycle rule for the `html/` prefix with a 90-day expiration period.
2. WHEN a stored HTML file expires due to the lifecycle rule, THE History_Page SHALL handle the `HTML_NOT_FOUND` error gracefully by disabling the Re-run button for that job.

### Requirement 6: Re-run with Images ZIP

**User Story:** As a user, I want re-runs to use the original images ZIP if one was provided, so that the re-annotated PDF renders images correctly.

#### Acceptance Criteria

1. WHEN the Processor_Lambda processes a job that includes an `images_s3_key`, THE Processor_Lambda SHALL NOT delete the uploaded images ZIP from S3 in the `finally` cleanup block, and SHALL instead copy it to a persistent location at `html/{job_id}/images.zip`.
2. WHEN the Processor_Lambda processes a re-run request for a job that has a stored images ZIP at `html/{rerun_job_id}/images.zip`, THE Processor_Lambda SHALL use that images ZIP for image path rewriting.
3. IF the stored images ZIP for a re-run job does not exist in S3, THEN THE Processor_Lambda SHALL proceed with the re-run without images, since the original job may not have included an images ZIP.
