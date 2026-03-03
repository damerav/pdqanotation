import json
import boto3

bedrock = boto3.client("bedrock-runtime")
MODEL_ID = "us.anthropic.claude-3-haiku-20240307-v1:0"

SYSTEM = """You are an email marketing analyst. Classify each hyperlink from an HTML email campaign.

For every link return:
- label: short human-readable label (e.g. "Header Logo", "Primary CTA", "Prescribing Information",
  "View Online", "Contact Us", "Unsubscribe", "Privacy Policy", "Terms & Conditions")
- include: true for user-facing content links; false for font stylesheets, tracking pixels, or duplicates

Return ONLY a JSON object: {"links": [{"label": "...", "include": true/false}, ...]}
One entry per input link, same order."""


def classify_links(raw_links: list[dict]) -> list[dict]:
    if not raw_links:
        return []

    payload = json.dumps([
        {"url": l["url"], "anchor_text": l["anchor_text"], "context": l["context"][:150]}
        for l in raw_links
    ])

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": f"Classify these links:\n{payload}"}],
    })

    try:
        resp = bedrock.invoke_model(modelId=MODEL_ID, body=body)
        text = json.loads(resp["body"].read())["content"][0]["text"]
        classifications = json.loads(text).get("links", [])
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
