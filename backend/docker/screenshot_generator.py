"""
screenshot_generator.py

Captures desktop (1200px) and mobile (390px) screenshots of HTML email content.
Returns screenshots + link bounding boxes for badge placement.
"""

import base64
import json
import os
from urllib import request as urllib_request
from urllib.error import URLError

SCREENSHOT_SERVICE_URL = os.environ.get("SCREENSHOT_SERVICE_URL", "")


def capture_screenshots(
    html_content: str,
    work_dir: str | None = None,
    images_b64: dict[str, str] | None = None,
) -> tuple[bytes, bytes, list[dict], list[dict]]:
    """Capture screenshots and link bounding boxes via the EC2 service."""
    if not SCREENSHOT_SERVICE_URL:
        raise RuntimeError("SCREENSHOT_SERVICE_URL not set.")

    url = f"{SCREENSHOT_SERVICE_URL.rstrip('/')}/screenshot"
    payload_dict: dict = {"html_content": html_content}
    if images_b64:
        payload_dict["images"] = images_b64

    payload = json.dumps(payload_dict).encode("utf-8")

    req = urllib_request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        raise RuntimeError(f"Screenshot service unreachable: {e}") from e

    if "error" in data:
        raise RuntimeError(f"Screenshot service error: {data['error']}")

    desktop_bytes = base64.b64decode(data["desktop"])
    mobile_bytes = base64.b64decode(data["mobile"])
    desktop_links = data.get("desktop_links", [])
    mobile_links = data.get("mobile_links", [])

    print(f"[INFO] Desktop screenshot: {len(desktop_bytes)} bytes, {len(desktop_links)} link bboxes")
    print(f"[INFO] Mobile screenshot: {len(mobile_bytes)} bytes, {len(mobile_links)} link bboxes")

    return desktop_bytes, mobile_bytes, desktop_links, mobile_links
