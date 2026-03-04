#!/bin/bash
set -ex

apt-get update -y
apt-get install -y python3-pip python3-venv

mkdir -p /opt/screenshot-service
cd /opt/screenshot-service

python3 -m venv venv
source venv/bin/activate

pip install flask playwright gunicorn
playwright install --with-deps chromium

cat > /opt/screenshot-service/app.py << 'PYEOF'
import os
import re
import tempfile
import shutil
import base64
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/screenshot", methods=["POST"])
def screenshot():
    data = request.get_json(force=True)
    html_content = data.get("html_content", "")
    images = data.get("images", {})
    if not html_content:
        return jsonify({"error": "html_content required"}), 400
    try:
        desktop_b64, mobile_b64 = _capture(html_content, images)
        return jsonify({"desktop": desktop_b64, "mobile": mobile_b64}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _capture(html_content, images):
    work_dir = tempfile.mkdtemp(prefix="screenshot_")
    try:
        if images:
            for rel_path, b64_data in images.items():
                img_path = os.path.join(work_dir, rel_path)
                os.makedirs(os.path.dirname(img_path), exist_ok=True)
                with open(img_path, "wb") as f:
                    f.write(base64.b64decode(b64_data))
            html_content = _rewrite_file_paths(html_content, work_dir, images)

        html_path = os.path.join(work_dir, "email_render.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        file_url = f"file://{html_path}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            desktop_page = browser.new_page(viewport={"width": 1200, "height": 900})
            desktop_page.goto(file_url, wait_until="load", timeout=30000)
            desktop_page.wait_for_timeout(2000)
            desktop_bytes = desktop_page.screenshot(full_page=True)
            desktop_page.close()
            mobile_page = browser.new_page(viewport={"width": 390, "height": 844})
            mobile_page.goto(file_url, wait_until="load", timeout=30000)
            mobile_page.wait_for_timeout(2000)
            mobile_bytes = mobile_page.screenshot(full_page=True)
            mobile_page.close()
            browser.close()
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
    return (
        base64.b64encode(desktop_bytes).decode("ascii"),
        base64.b64encode(mobile_bytes).decode("ascii"),
    )

def _rewrite_file_paths(html_content, work_dir, images):
    image_map = {}
    for rel_path in images.keys():
        abs_path = os.path.join(work_dir, rel_path)
        parts = rel_path.replace("\\\\", "/").lower().split("/")
        for i in range(len(parts)):
            sub = "/".join(parts[i:])
            if sub not in image_map:
                image_map[sub] = abs_path

    def _replace_src(match):
        prefix = match.group(1)
        original = match.group(2)
        suffix = match.group(3)
        if original.startswith("file://"):
            path_part = original.replace("file://", "")
            basename = os.path.basename(path_part).lower()
            if basename in image_map:
                return f'{prefix}file://{image_map[basename]}{suffix}'
            norm = path_part.replace("\\\\", "/").lower()
            for key, val in image_map.items():
                if norm.endswith(key):
                    return f'{prefix}file://{val}{suffix}'
            return match.group(0)
        if original.startswith(("data:", "http://", "https://")):
            return match.group(0)
        lookup = original.replace("\\\\", "/").lower().lstrip("./")
        if lookup in image_map:
            return f'{prefix}file://{image_map[lookup]}{suffix}'
        return match.group(0)

    html_content = re.sub(
        r'(src\s*=\s*["\'])([^"\']+)(["\'])',
        _replace_src, html_content, flags=re.IGNORECASE)

    def _replace_css_url(match):
        prefix = match.group(1)
        quote = match.group(2) or ""
        original = match.group(3)
        suffix = match.group(4)
        if original.startswith("file://"):
            path_part = original.replace("file://", "")
            basename = os.path.basename(path_part).lower()
            if basename in image_map:
                return f'{prefix}{quote}file://{image_map[basename]}{quote}{suffix}'
            return match.group(0)
        if original.startswith(("data:", "http://", "https://")):
            return match.group(0)
        lookup = original.replace("\\\\", "/").lower().lstrip("./")
        if lookup in image_map:
            return f'{prefix}{quote}file://{image_map[lookup]}{quote}{suffix}'
        return match.group(0)

    html_content = re.sub(
        r'(url\s*\()(["\']?)([^)\'"]+)(["\']?\))',
        _replace_css_url, html_content, flags=re.IGNORECASE)
    return html_content

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
PYEOF

cat > /etc/systemd/system/screenshot.service << 'SVCEOF'
[Unit]
Description=Screenshot Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/screenshot-service
ExecStart=/opt/screenshot-service/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 --timeout 120 app:app
Restart=always

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable screenshot
systemctl start screenshot
