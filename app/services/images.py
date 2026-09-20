from pathlib import Path
from urllib.parse import urlparse
import httpx

async def download_image(url: str, directory: str, name: str) -> str:
    if not url.startswith(("http://", "https://")):
        return url
    target_dir = Path(directory); target_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    content_type = response.headers.get("content-type", "").split(";")[0].lower()
    extensions = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
    extension = extensions.get(content_type, Path(urlparse(str(response.url)).path).suffix or ".jpg")
    if extension not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        extension = ".jpg"
    if len(response.content) > 10 * 1024 * 1024:
        raise ValueError("Изображение превышает лимит 10 МБ")
    path = target_dir / f"{name}{extension}"
    path.write_bytes(response.content)
    return str(path)
