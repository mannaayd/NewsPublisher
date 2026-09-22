import httpx
import re
from html import unescape

async def extract(base_url: str, url: str) -> dict:
    async with httpx.AsyncClient(timeout=40) as client:
        health = await client.get(f"{base_url}/health"); health.raise_for_status()
        response = await client.post(f"{base_url}/v1/extract", json={"url": url, "selectors": {"article": 'article[aria-labelledby="accessibility-article"]'}, "timeout": 30, "max_elements_per_selector": 1})
        response.raise_for_status(); data = response.json()
    element = data.get("results", {}).get("article", {}).get("elements", [{}])[0]
    text = element.get("text", "").strip()
    if not text: raise ValueError("Scrapit вернул пустой текст статьи")
    html = element.get("html", "")
    image = None
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        page = await client.get(url, headers={"User-Agent": "NewsPublisher/1.0"})
        if page.is_success:
            og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', page.text, re.I)
            if not og:
                og = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', page.text, re.I)
            image = unescape(og.group(1)) if og else None
    match = re.search(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)', html, re.I)
    if not image and match:
        image = match.group(1)
        if image.startswith("//"): image = "https:" + image
    return {"text": text, "html": html, "image_url": image}
