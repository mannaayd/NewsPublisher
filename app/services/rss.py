import feedparser
import httpx
import re

async def fetch(url: str) -> list[dict]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(url); response.raise_for_status()
    parsed = feedparser.parse(response.text)
    result = []
    for entry in parsed.entries:
        link = entry.get("link")
        if not link: continue
        image = None
        if entry.get("media_content"):
            image = entry.media_content[0].get("url")
        elif entry.get("media_thumbnail"):
            image = entry.media_thumbnail[0].get("url")
        elif entry.get("enclosures"):
            image = entry.enclosures[0].get("href") or entry.enclosures[0].get("url")
        if not image:
            html = entry.get("summary", "") or entry.get("description", "")
            match = re.search(r'<img[^>]+src=["\']([^"\']+)', html, re.I)
            image = match.group(1) if match else None
        result.append({"guid": entry.get("id") or link, "url": link, "title": entry.get("title", "Без заголовка"), "description": entry.get("summary", ""), "published_at": entry.get("published", ""), "image_url": image})
    return result
