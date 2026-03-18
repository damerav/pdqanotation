from bs4 import BeautifulSoup

SKIP = ["fonts.googleapis.com", "fonts.gstatic.com", "mailto:", "tel:", "javascript:"]


def extract_links(html_content: str) -> list[dict]:
    """Extract unique links from HTML, keeping duplicates with different anchor text."""
    soup = BeautifulSoup(html_content, "lxml")
    seen: set[tuple[str, str]] = set()
    links: list[dict] = []

    for tag in soup.find_all("a", href=True):
        url = tag["href"].strip()
        if not url or url.startswith("#"):
            continue
        if any(p in url for p in SKIP):
            continue

        anchor = tag.get_text(strip=True)
        # Deduplicate by (url, anchor_text) pair — same URL with different
        # anchor text represents a different visual element in the email
        key = (url, anchor.lower())
        if key in seen:
            continue

        parent = tag.parent
        context = (parent.get_text(separator=" ", strip=True)[:200] if parent else "")

        links.append({"url": url, "anchor_text": anchor, "context": context})
        seen.add(key)

    return links
