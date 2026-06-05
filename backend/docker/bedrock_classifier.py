import json
import re
from urllib.parse import urlparse

import boto3

bedrock = boto3.client("bedrock-runtime")

# Amazon Nova Micro — fast, cheap, good for structured JSON output
MODEL_ID = "amazon.nova-micro-v1:0"

SYSTEM = """You are an email marketing analyst. Classify each hyperlink from an HTML email campaign.

For every link return:
- label: short human-readable label (e.g. "Header Logo", "Primary CTA", "Prescribing Information",
  "View Online", "Contact Us", "Unsubscribe", "Privacy Policy", "Terms & Conditions")
- include: true or false (see rules below)

INCLUSION RULES — follow these strictly:
- include: true for ALL user-facing content links, including:
  - Image-only links with empty anchor text (these are clickable visual elements, use img_alt for label context)
  - Generic CTA text such as "Click here", "Learn more", "Read more", "Shop now" (these are valid call-to-action links)
  - Ghost-link CSS overlays (these are intentional clickable regions over visual content)
  - Any <a href> a user can click to navigate somewhere
- include: false ONLY for:
  - Font stylesheets (e.g. fonts.googleapis.com, fonts.gstatic.com)
  - 1x1 tracking pixels with no clickable area
  - Protocol-only links (mailto:, tel:, javascript:)

When in doubt, set include: true. It is better to include a borderline link than to miss a valid one.

Return ONLY a JSON object: {"links": [{"label": "...", "include": true/false}, ...]}
One entry per input link, same order."""


def _is_generic_label(label: str) -> bool:
    """Return True if label matches the generic 'Link N' pattern."""
    return bool(re.match(r'^Link\s+\d+$', label))


# Hosts whose URL paths are opaque tracking/redirect identifiers rather than
# human-readable content names (e.g. ad-server click trackers, ESP redirects).
_TRACKING_HOST_HINTS = (
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "google-analytics.com",
    "links.",
    "click.",
    "trk.",
    "track.",
    "email.",
)

# URL path segments that are ad-server verbs, not content names.
_TRACKING_PATH_HINTS = {"clk", "trackclk", "ddm", "aclk", "redirect", "r", "e"}

_FILE_EXT_RE = re.compile(r"\.(html?|php|aspx?|jsp|pdf|cfm)$", re.IGNORECASE)


def _normalize_text(value: str) -> str:
    """Collapse non-breaking/zero-width spaces and trim surrounding whitespace."""
    return value.replace("\xa0", " ").replace("\u200b", "").strip()


def _is_opaque_segment(segment: str) -> bool:
    """Return True if a URL path segment is an opaque ID, not a readable word."""
    seg = _FILE_EXT_RE.sub("", segment)
    if not seg:
        return True
    # Purely numeric / punctuation (e.g. "621883234", "438708548", "12.34-5")
    if re.fullmatch(r"[\d.\-_]+", seg):
        return True
    # ID-like: contains a digit and its letters have no vowels (e.g. "B35118264")
    letters = re.sub(r"[^A-Za-z]", "", seg)
    if any(ch.isdigit() for ch in seg) and not re.search(r"[aeiou]", letters, re.IGNORECASE):
        return True
    return False


def _label_from_url(url: str) -> str | None:
    """Derive a readable label from a URL path or domain, or None if opaque."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if any(hint in host for hint in _TRACKING_HOST_HINTS):
        return None
    for raw_segment in reversed([s for s in parsed.path.split("/") if s]):
        segment = raw_segment.split(";")[0].split("?")[0]
        if segment.lower() in _TRACKING_PATH_HINTS:
            continue
        if _is_opaque_segment(segment):
            continue
        return segment.replace("-", " ").replace("_", " ").strip().title()[:60]
    if host:
        return host[4:] if host.startswith("www.") else host
    return None


def _label_from_context(context: str) -> str | None:
    """Derive a short label from surrounding text context, or None if unusable."""
    text = _normalize_text(context)
    if len(text) < 3:
        return None
    # Use the first clause / sentence fragment, capped to a readable length.
    fragment = re.split(r"[.!?\n]", text, maxsplit=1)[0].strip()
    words = fragment.split()
    if not words:
        return None
    return " ".join(words[:8])[:60]


def derive_label_from_metadata(link: dict, index: int = 0) -> str:
    """Derive a meaningful label from link metadata.

    Priority order:
    1. anchor_text (non-empty, normalised, truncated to 60 chars)
    2. img_alt (non-empty, normalised)
    3. URL path/domain (skipping opaque IDs and ad-redirect/tracking hosts)
    4. surrounding text context (first clause)
    5. "Link {index+1}" as last resort
    """
    anchor = _normalize_text(link.get("anchor_text", ""))
    if anchor:
        return anchor[:60]

    img_alt = _normalize_text(link.get("img_alt", ""))
    if img_alt:
        return img_alt[:60]

    url = link.get("url", "")
    if url:
        url_label = _label_from_url(url)
        if url_label:
            return url_label

    context_label = _label_from_context(link.get("context", ""))
    if context_label:
        return context_label

    return f"Link {index + 1}"


def classify_links(raw_links: list[dict]) -> list[dict]:
    """Classify email links using Amazon Nova Micro via Bedrock."""
    if not raw_links:
        return []

    def _build_link_payload(l: dict) -> dict:
        """Build classifier payload for a single link, including img_alt when present."""
        entry = {"url": l["url"], "anchor_text": l["anchor_text"], "context": l["context"][:500]}
        if l.get("img_alt"):
            entry["img_alt"] = l["img_alt"]
        return entry

    payload = json.dumps([_build_link_payload(l) for l in raw_links])

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
        # Post-process: replace generic "Link N" labels with metadata-derived labels
        for i, clf in enumerate(classifications):
            if _is_generic_label(clf.get("label", "")):
                clf["label"] = derive_label_from_metadata(raw_links[i], i) if i < len(raw_links) else clf["label"]
    except Exception as e:
        print(f"[WARN] Bedrock classification failed: {e}. Using fallback labels.")
        classifications = [{"label": derive_label_from_metadata(link, i), "include": True} for i, link in enumerate(raw_links)]

    result = []
    for i, link in enumerate(raw_links):
        clf = classifications[i] if i < len(classifications) else {"label": derive_label_from_metadata(raw_links[i], i), "include": True}
        if clf.get("include", True):
            result.append({**link, "label": clf["label"]})

    return result


def assign_letters(classified_links: list[dict], bboxes: list[dict] | None = None) -> list[dict]:
    """Assign letter labels (A, B, C...) to classified links in visual or source order.

    When bboxes are provided, links are matched to bounding boxes by URL
    (and anchor text for disambiguation) and sorted by ascending center_y
    so letters follow visual top-to-bottom order.

    When bboxes are None, links are sorted by element_index (source order)
    and letters are assigned sequentially.
    """
    if not classified_links:
        return []

    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    if bboxes:
        # Build lookup: href -> list of bboxes
        bbox_by_href: dict[str, list[dict]] = {}
        for bb in bboxes:
            href = bb.get("href", "")
            if href:
                bbox_by_href.setdefault(href, []).append(bb)

        # Match each link to a bbox and attach center_y for sorting
        augmented: list[tuple[float, int, dict]] = []
        used_bboxes: set[int] = set()

        for idx, link in enumerate(classified_links):
            url = link.get("url", "")
            anchor = link.get("anchor_text", "").strip().lower()
            candidates = bbox_by_href.get(url, [])

            matched_bb = None
            # Prefer text-match for disambiguation of duplicate URLs
            for bb in candidates:
                bb_id = id(bb)
                if bb_id in used_bboxes:
                    continue
                bb_text = bb.get("text", "").strip().lower()
                if anchor and bb_text and (anchor in bb_text or bb_text in anchor):
                    matched_bb = bb
                    used_bboxes.add(bb_id)
                    break

            if matched_bb is None:
                for bb in candidates:
                    bb_id = id(bb)
                    if bb_id not in used_bboxes:
                        matched_bb = bb
                        used_bboxes.add(bb_id)
                        break

            if matched_bb:
                center_y = matched_bb.get("center_y", 0.0)
            else:
                # No bbox match — use element_index as fallback sort key
                center_y = float(link.get("element_index", idx)) * 1000.0

            augmented.append((center_y, idx, link))

        # Sort by center_y ascending (visual top-to-bottom)
        augmented.sort(key=lambda t: (t[0], t[1]))

        result = []
        for i, (_, _, link) in enumerate(augmented):
            result.append({**link, "letter": letters[i % 26]})
        return result
    else:
        # No bboxes — fall back to source order via element_index
        sorted_links = sorted(
            classified_links,
            key=lambda l: l.get("element_index", 0),
        )
        result = []
        for i, link in enumerate(sorted_links):
            result.append({**link, "letter": letters[i % 26]})
        return result
