from bs4 import BeautifulSoup

SKIP = ["fonts.googleapis.com", "fonts.gstatic.com", "mailto:", "tel:", "javascript:"]


def extract_links(html_content: str) -> list[dict]:
    """Extract unique links from HTML, keeping duplicates with different anchor text."""
    soup = BeautifulSoup(html_content, "lxml")
    seen: set[tuple] = set()
    links: list[dict] = []
    element_index = 0

    for tag in soup.find_all("a", href=True):
        url = tag["href"].strip()
        if not url or url.startswith("#"):
            continue
        if any(p in url for p in SKIP):
            continue

        anchor = tag.get_text(strip=True)

        # When anchor text is empty, include element_index in the dedup key
        # so that image-wrapped links sharing the same URL are treated as distinct.
        # When anchor text is non-empty, use (url, anchor) to preserve same-text dedup.
        if anchor:
            key = (url, anchor.lower())
        else:
            key = (url, anchor.lower(), element_index)

        if key in seen:
            element_index += 1
            continue

        parent = tag.parent
        context = (parent.get_text(separator=" ", strip=True)[:200] if parent else "")

        link_dict: dict = {
            "url": url,
            "anchor_text": anchor,
            "context": context,
            "element_index": element_index,
        }

        # Extract <img> child alt attribute when anchor text is empty
        if not anchor:
            img_tag = tag.find("img")
            if img_tag and img_tag.get("alt"):
                link_dict["img_alt"] = img_tag["alt"]

        links.append(link_dict)
        seen.add(key)
        element_index += 1

    return links
