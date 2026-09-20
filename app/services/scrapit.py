import httpx
import re

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
    match = re.search(r'<img[^>]+(?:src|data-src)=["\']([^"\']+)', html, re.I)
    if match:
        image = match.group(1)
        if image.startswith("//"): image = "https:" + image
    return {"text": text, "html": html, "image_url": image}
