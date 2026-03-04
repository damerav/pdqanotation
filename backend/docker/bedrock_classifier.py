import json
import re
import boto3

bedrock = boto3.client("bedrock-runtime")

# Amazon Nova Micro — fast, cheap, good for structured JSON output
MODEL_ID = "amazon.nova-micro-v1:0"

SYSTEM = """You are an email marketing analyst. Classify each hyperlink from an HTML email campaign.

For every link return:
- label: short human-readable label (e.g. "Header Logo", "Primary CTA", "Prescribing Information",
  "View Online", "Contact Us", "Unsubscribe", "Privacy Policy", "Terms & Conditions")
- include: true for user-facing content links; false for font stylesheets, tracking pixels, or duplicates

Return ONLY a JSON object: {"links": [{"label": "...", "include": true/false}, ...]}
One entry per input link, same order."""


def classify_links(raw_links: list[dict]) -> list[dict]:
    """Classify email links using Amazon Nova Micro via Bedrock."""
    if not raw_links:
        return []

    payload = json.dumps([
        {"url": l["url"], "anchor_text": l["anchor_text"], "context": l["context"][:150]}
        for l in raw_links
    ])

    body = json.dumps({
        "inferenceConfig": {"maxTokens": 1024},
        "system": [{"text": SYSTEM}],
        "messages": [{"role": "user", "content": [
            {"text": f"Classify these links:\n{payload}"}
        ]}],
    })

    try:
        resp = bedrock.invoke_model(modelId=MODEL_ID, body=body)
        raw = json.loads(resp["body"].read(), strict=False)
        text = raw["output"]["message"]["content"][0]["text"]
        # Strip accidental markdown code fences
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        # Remove stray control characters
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', text)
        classifications = json.loads(text, strict=False).get("links", [])
    except Exception as e:
        print(f"[WARN] Bedrock classification failed: {e}. Using fallback labels.")
        classifications = [{"label": f"Link {i+1}", "include": True} for i in range(len(raw_links))]

    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result, idx = [], 0
    for i, link in enumerate(raw_links):
        clf = classifications[i] if i < len(classifications) else {"label": f"Link {i+1}", "include": True}
        if clf.get("include", True):
            result.append({**link, "label": clf["label"], "letter": letters[idx % 26]})
            idx += 1

    return result
