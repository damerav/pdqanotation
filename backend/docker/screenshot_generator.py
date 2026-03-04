"""
screenshot_generator.py

Captures desktop (1200px) and mobile (390px) screenshots of HTML email content.

Delegates to an EC2-hosted Flask microservice running Playwright + Chromium.
The Lambda sends HTML content via HTTP POST and receives base64-encoded PNGs.
"""

import base64
import json
import os
from urllib import request as urllib_request
from urllib.error import URLError

SCREENSHOT_SERVICE_URL = os.environ.get("SCREENSHOT_SERVICE_URL", "")


def capture_screenshots(
    html_content: str, work_dir: str | None = None
) -> tuple[bytes, bytes]:
    """Capture desktop and mobile screenshots via the EC2 screenshot service."""
    if not SCREENSHOT_SERVICE_URL:
        raise RuntimeError(
            "SCREENSHOT_SERVICE_URL not set. Cannot capture screenshots."
        )

    url = f"{SCREENSHOT_SERVICE_URL.rstrip('/')}/screenshot"
    payload = json.dumps({"html_content": html_content}).encode("utf-8")

    req = urllib_request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        raise RuntimeError(f"Screenshot service unreachable: {e}") from e

    if "error" in data:
        raise RuntimeError(f"Screenshot service error: {data['error']}")

    desktop_bytes = base64.b64decode(data["desktop"])
    mobile_bytes = base64.b64decode(data["mobile"])

    print(f"[INFO] Desktop screenshot: {len(desktop_bytes)} bytes")
    print(f"[INFO] Mobile screenshot: {len(mobile_bytes)} bytes")

    return desktop_bytes, mobile_bytes
