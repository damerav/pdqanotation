from bs4 import BeautifulSoup

SKIP = ["fonts.googleapis.com", "fonts.gstatic.com", "mailto:", "tel:", "javascript:"]


def extract_links(html_content: str) -> list[dict]:
    soup = BeautifulSoup(html_content, "lxml")
    seen, links = set(), []

    for tag in soup.find_all("a", href=True):
        url = tag["href"].strip()
        if not url or url in seen or url.startswith("#"):
            continue
        if any(p in url for p in SKIP):
            continue

        anchor = tag.get_text(strip=True)
        parent = tag.parent
        context = (parent.get_text(separator=" ", strip=True)[:200] if parent else "")

        links.append({"url": url, "anchor_text": anchor, "context": context})
        seen.add(url)

    return links
