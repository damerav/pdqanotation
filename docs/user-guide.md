# Email Campaign Annotator — User Guide

Welcome to the Email Campaign Annotator. This guide walks you through everything you need to know to upload HTML emails, receive AI-powered quality reviews, and download annotated PDF proofs — all in about 60 seconds.

---

## Table of Contents

1. [What the Tool Does](#what-the-tool-does)
2. [How to Log In](#how-to-log-in)
3. [File Requirements](#file-requirements)
4. [The Upload Form](#the-upload-form)
5. [What Happens After Submission](#what-happens-after-submission)
6. [How to Read the PDF](#how-to-read-the-pdf)
7. [The Delivery Email](#the-delivery-email)
8. [History Page](#history-page)
9. [FAQ](#faq)
10. [Troubleshooting](#troubleshooting)

---

## What the Tool Does

The Email Campaign Annotator replaces the manual proof-creation workflow you may be used to — the one that involves bouncing between Outlook, Dreamweaver, Email on Acid, and Adobe InDesign. That process typically takes around 13 minutes per email. This tool brings it down to about 60 seconds.

Here is what happens when you use it:

1. You upload your HTML email file through the web app.
2. The system extracts every hyperlink from the HTML and sends them to an AI model (Claude 3 Haiku) that classifies each link with a human-readable label like "Primary CTA", "Prescribing Information", or "Unsubscribe".
3. A second, more thorough AI model (Claude 3 Sonnet) reviews the entire email for quality issues across six categories: Links, Accessibility, Compliance, Content, Deliverability, and Technical. It assigns a quality score from 0 to 100.
4. The system captures two screenshots of your email — one at desktop width (1200 px, simulating Outlook / Microsoft 365) and one at mobile width (390 px, simulating an iPhone 14).
5. Lettered callout badges (A, B, C, etc.) are overlaid on each screenshot, marking every link in the email.
6. Everything is assembled into a multi-page PDF: the AI review report, the annotated desktop screenshot, the annotated mobile screenshot, and a link reference table.
7. The PDF is emailed directly to you (or to a colleague of your choice) with a summary of the review results.

You get a professional, ready-to-share proof without opening a single design tool.

---

## How to Log In

Accounts are created by your administrator — there is no self-registration. Your admin will provide you with a temporary password.

1. Open the web app URL in your browser (your admin will share this link with you).
2. Enter your email address and the temporary password you were given.
3. On your first login, you will be prompted to set a new password. Choose something you will remember — it must meet the minimum complexity requirements shown on screen.
4. After setting your new password, you will be signed in and taken to the Upload page.

If you forget your password, contact your administrator to reset it.

Your session will stay active while you are using the app. If you step away for an extended period, you may need to sign in again.

---

## File Requirements

The tool accepts HTML email files only. Before uploading, make sure your file meets these requirements:

| Requirement | Details |
|---|---|
| File type | `.html` files only |
| Maximum size | 5 MB |
| Encoding | UTF-8 |
| Valid HTML | File must begin with a recognized HTML tag: `<html`, `<!DOCTYPE`, `<head`, or `<body` |

Files that do not meet these requirements will be rejected with an error message.

The tool does not accept `.eml`, `.msg`, `.mjml`, or any other email format. If your email is in one of those formats, export or save it as a plain `.html` file first.

---

## The Upload Form

After signing in, you land on the Upload page. The form has four fields:

### File Upload

The large drop zone at the top of the form is where you provide your HTML file. You can either:

- Drag and drop the file from your desktop or file explorer directly onto the drop zone, or
- Click anywhere inside the drop zone to open a file browser and select the file.

Only `.html` files are accepted. Once a file is selected, you will see a confirmation showing the filename and file size (e.g., "✅ campaign-email.html (42.3 KB)").

### Subject Line (optional)

Enter the email's subject line, for example: `Bayer Kerendia Pharmacy — PDQ-PEM-25-075`. This is included in the PDF header and the delivery email for easy identification. If you leave it blank, the PDF will still generate — it just won't show a subject line.

### Preheader Text (optional)

Enter the email's preheader text, for example: `NEW! KERENDIA Blister Packs Now Available`. Like the subject line, this appears in the PDF header for reference. It is also sent to the AI reviewer so it can check for subject/preheader consistency.

### Deliver PDF to Email

This field defaults to the email address you used to sign in. If you want the PDF sent to a colleague or a shared mailbox instead, change the address here. The PDF and review summary will be delivered to whichever address is in this field.

When everything looks right, click the "Generate Annotated PDF" button.

---

## What Happens After Submission

Once you click "Generate Annotated PDF", the button changes to "Processing…" and a status banner appears:

> ⏳ Uploading and reviewing your email — this takes about 30–60 seconds…

During this time, the system is running through the full pipeline: parsing links, classifying them with AI, performing the quality review, capturing screenshots, annotating them, building the PDF, uploading it, and sending the email. Do not close the browser tab while processing is in progress.

### On Success

When processing completes, the status banner is replaced by a Review Result card showing:

- **Quality score** — a large number from 0 to 100, color-coded for quick reading:
  - Green (80–100): The email is in good shape. Minor suggestions may still appear.
  - Amber (60–79): There are issues worth addressing before sending.
  - Red (0–59): Significant problems were found. Review the PDF carefully.
- **Review summary** — a two- to three-sentence overview of the email's quality written by the AI.
- **Issue counts** — the number of critical issues, warnings, and informational notes found.
- **Email confirmation** — a message confirming the annotated PDF was sent to the specified email address.

### On Error

If something goes wrong, a red error banner appears with a description of the problem. See the [Troubleshooting](#troubleshooting) section for common errors and how to fix them.

---

## How to Read the PDF

The annotated PDF has four pages. Here is what each one contains and how to read it.

### Page 1 — Review Report

This is the AI-generated quality review of your email.

At the top of the page you will see:

- The **subject line** and **preheader text** (if you provided them).
- A large **quality score** (0–100), color-coded green, amber, or red.
- A count of issues by severity: critical, warnings, and info.
- An **overall summary** — a brief paragraph describing the email's strengths and weaknesses.

Below the summary is the **issues table**, grouped by category:

| Category | What It Covers |
|---|---|
| Links | Broken URLs, placeholder links, missing UTM parameters, duplicate links |
| Accessibility | Missing alt text on images, non-descriptive link text, missing lang attribute, layout tables without role="presentation" |
| Compliance | CAN-SPAM requirements (unsubscribe link, physical address), pharmaceutical disclosure links, deceptive subject lines |
| Content | Placeholder text, spam trigger words, excessive caps or exclamation marks, weak calls-to-action |
| Deliverability | Image-to-text ratio, spam keywords, HTML file size concerns |
| Technical | Unsupported CSS properties, missing viewport meta tag, use of JavaScript, deeply nested tables |

Each issue in the table shows:

- A **severity badge**: red for critical, amber for warning, blue for info.
- The **issue title** — a short description of the problem.
- A **description** — why this issue matters.
- A **recommendation** — a specific, actionable suggestion for how to fix it.

### Page 2 — Desktop View

This page shows an annotated screenshot of your email rendered at 1200 pixels wide, simulating how it would appear in Outlook or Microsoft 365 on a desktop computer.

Red circles with white letters (A, B, C, D, etc.) are placed along the right side of the screenshot, each one marking a hyperlink in the email. These letters correspond to the entries in the Link Reference Table on Page 4.

### Page 3 — Mobile View

This page shows an annotated screenshot of your email rendered at 390 pixels wide, simulating how it would appear on an iPhone 14.

The same lettered callout badges appear here, marking the same links as on the desktop view. This lets you verify that links are visible and tappable on a small screen.

### Page 4 — Link Reference Table

This is a complete table listing every annotated link in the email. Each row contains:

| Column | Description |
|---|---|
| Ref | The letter (A, B, C, etc.) that matches the callout badge on the screenshots |
| Label | An AI-generated description of the link's purpose, such as "Primary CTA", "Header Logo", "Prescribing Information", or "Unsubscribe" |
| URL | The full destination URL of the link |

Use this table to cross-reference the callout badges on Pages 2 and 3 with the actual URLs. This is especially useful when reviewing links with your compliance or regulatory team.

---

## The Delivery Email

After processing completes, an email is sent to the address you specified in the form. Here is what to expect:

- **Subject line format**: `Email Review Complete — [Your Subject Line] [Score/100]`
  For example: `Email Review Complete — Bayer Kerendia Pharmacy — PDQ-PEM-25-075 [82/100]`
- **Quality score** displayed prominently with color coding.
- **Review summary** — the same two- to three-sentence overview from the PDF.
- **Issue counts** — critical, warnings, and info totals.
- **Top 5 issues** — a table showing the five most important issues with severity badges, titles, and categories.
- **"Download Annotated PDF" button** — a prominent red button that links directly to the PDF file.
- **Expiry notice** — a note that the PDF link expires in 7 days.

If you need to share the proof with a colleague, you can forward this email. The PDF download link will work for anyone who has it, for up to 7 days.

---

## History Page

Click the "History" tab at the top of the app to see all your past annotation jobs, sorted with the most recent first.

Each job card shows:

- **Score circle** — the quality score with color coding (green, amber, or red). Shows "—" if the AI review was unavailable.
- **Filename** — the name of the HTML file you uploaded.
- **Status badge** — shows "done" for completed jobs.
- **Subject line** — if you provided one when uploading.
- **Review summary** — a brief excerpt of the AI's assessment.
- **Issue counts** — critical, warnings, and info totals (only shown if issues were found).
- **Timestamp** — the date and time the job was processed.
- **Download PDF link** — click "↓ PDF" to download the annotated PDF directly.

Use the **↻ Refresh** button in the top-right corner to reload the list if you have just submitted a new job and it has not appeared yet.

**Important**: PDF download links expire after 7 days. After that, the link on the job card will no longer work. If you need the PDF again, re-upload the HTML file to generate a new one. The job record itself (filename, score, summary) remains on the History page indefinitely.

---

## FAQ

### 1. What file types can I upload?

HTML files only (`.html` extension). The tool does not accept `.eml`, `.msg`, `.mjml`, `.txt`, or any other format. If your email is in a different format, export or save it as HTML first.

### 2. How long does processing take?

Most emails are processed in 30 to 60 seconds. Very large or complex HTML files (close to the 5 MB limit) may take longer — up to 5 minutes in rare cases. Do not close the browser tab while processing is in progress.

### 3. Can I send the PDF to someone else?

Yes. Change the "Deliver PDF to Email" field on the upload form to any email address you like. The PDF and review summary will be sent there instead of to your own inbox. You can also forward the delivery email after you receive it — the PDF download link works for anyone.

### 4. Why did my score change between runs?

The AI review may produce slightly different results each time, even for the same HTML file. This is normal behavior for AI models. The differences are usually minor (a few points). If you see a large change, it is likely because the AI noticed something it missed before, or interpreted an edge case differently.

### 5. What does an "N/A" or "—" score mean?

This means the AI review service was temporarily unavailable when your job was processed. The PDF is still generated — it will include the annotated screenshots and link reference table — but the review report page will be empty. Try uploading the file again after a few minutes.

### 6. How long are PDF download links valid?

PDF links expire 7 days after the job was processed. After that, the link in the delivery email and on the History page will no longer work. If you need the PDF after 7 days, upload the HTML file again to generate a fresh one.

### 7. Can I re-download a PDF from a previous job?

Yes, as long as it has been fewer than 7 days since the job was processed. Go to the History page and click the "↓ PDF" link on the job card. After 7 days, the PDF file is automatically deleted and the link will no longer work.

### 8. Who can create my account?

Only your administrator can create accounts. There is no self-registration. If you need an account, or if a new team member needs access, contact your admin. They will set up the account and provide a temporary password.

### 9. What browsers are supported?

The web app works in all modern browsers: Google Chrome, Mozilla Firefox, Apple Safari, and Microsoft Edge. Use the latest version of your browser for the best experience. Internet Explorer is not supported.

### 10. Does the tool check if my links actually work?

Not in the current version. The AI reviews link URLs for obvious problems — placeholder text like "http://example.com" or "#", missing tracking parameters, and duplicate links — but it does not visit each URL to verify it loads correctly. Live link checking is planned for a future update.

---

## Troubleshooting

If you run into a problem, find the error message in the table below for guidance on how to fix it.

| Error Message | Cause | How to Fix |
|---|---|---|
| "html_content and recipient_email are required" | You submitted the form without selecting an HTML file, or the email field is empty. | Make sure you have selected an `.html` file in the upload zone and that the "Deliver PDF to Email" field contains a valid email address. |
| File is rejected after selection | The file does not have a `.html` extension, or it exceeds the 5 MB size limit. | Verify the file ends in `.html` (not `.htm`, `.eml`, or `.txt`). If the file is too large, try removing unnecessary comments or embedded images from the HTML source to reduce its size below 5 MB. |
| Processing takes longer than 2 minutes | The HTML file is very large or contains complex nested tables that take longer to render. | Wait up to 5 minutes. If it still has not completed, try simplifying the HTML (reduce image count, flatten nested tables) and upload again. |
| "Unauthorized" or 401 error | Your login session has expired. | Click "Sign Out" in the top-right corner, then sign back in with your email and password. |
| Score shows "N/A" or "—" | The AI review service (AWS Bedrock) was temporarily unavailable. | Your PDF was still generated with annotated screenshots and the link table, but without the review report. Upload the file again after a few minutes to get a full review. |
| PDF download link does not work | The 7-day expiry window has passed and the PDF file has been automatically deleted. | Go to the Upload page and re-upload the same HTML file to generate a new PDF. |
| "Could not load job history" | A network issue prevented the app from reaching the server. | Check your internet connection, then click the "↻ Refresh" button on the History page. If the problem persists, try signing out and back in. |
| Email with PDF not received | The delivery email may have been caught by your spam filter, or the recipient address may not be verified in the email system. | Check your spam or junk folder. Make sure the email address you entered is correct. If you still do not see it, contact your administrator — they may need to verify the recipient address in the email service. |
| Unexpected server error | An internal error occurred during processing. | Wait a minute and try uploading the file again. If the error repeats, note the error message and contact your administrator. |

---

*Last updated: 2025*
