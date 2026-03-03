import tempfile
import os
from playwright.sync_api import sync_playwright


def capture_screenshots(html_content: str, work_dir: str | None = None) -> tuple[bytes, bytes]:
    """Capture desktop and mobile screenshots of HTML content via Playwright."""
    # If work_dir is provided, write HTML there so relative image paths resolve.
    # Otherwise fall back to a random temp file.
    if work_dir:
        tmp_path = os.path.join(work_dir, "email_render.html")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    else:
        tmp_fd = tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8",
        )
        tmp_fd.write(html_content)
        tmp_path = tmp_fd.name
        tmp_fd.close()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            )

            # Desktop — Outlook-like 600px wide email client viewport
            desktop_ctx = browser.new_context(viewport={"width": 1200, "height": 900})
            desktop_page = desktop_ctx.new_page()
            desktop_page.goto(f"file://{tmp_path}", wait_until="networkidle")
            desktop_bytes = desktop_page.screenshot(full_page=True)
            desktop_ctx.close()

            # Mobile — iPhone 14 dimensions
            mobile_ctx = browser.new_context(viewport={"width": 390, "height": 844})
            mobile_page = mobile_ctx.new_page()
            mobile_page.goto(f"file://{tmp_path}", wait_until="networkidle")
            mobile_bytes = mobile_page.screenshot(full_page=True)
            mobile_ctx.close()

            browser.close()
    finally:
        # Clean up the temp HTML file, but NOT the work_dir — handler manages that
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return desktop_bytes, mobile_bytes
