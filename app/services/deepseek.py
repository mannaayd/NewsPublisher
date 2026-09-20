import json
import httpx

SYSTEM = """Ты редактор Telegram-канала. Перепиши статью на русском языке кратко, естественно и точно.

Правила:
- Не выдумывай факты.
- Не добавляй упоминание или ссылку на источник.
- Не упоминай искусственный интеллект, языковую модель, генерацию, промпты или процесс подготовки текста.
- Не используй длинное тире (—), среднее тире (–), декоративные разделители, повторяющиеся знаки, хэштеги и шаблонные фразы, по которым можно определить текст от ИИ.
- Используй обычную пунктуацию и короткие предложения.
- Не добавляй эмодзи без необходимости.
- Не начинай текст с фраз вроде «Вот краткий обзор», «В этой статье» или «Давайте разберёмся».
- Верни только JSON с ключами title, body_html, image_url.
- body_html должен использовать только Telegram HTML: b, i, u, s, a href. HTML-теги нужны только для форматирования и не считаются специальными символами текста."""

async def generate(api_key: str, model: str, title: str, text: str, source_url: str) -> dict:
    payload = {"model": model, "temperature": 0.4, "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Заголовок RSS: {title}\nИсточник: {source_url}\n\nТекст статьи:\n{text}"}]}
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post("https://api.deepseek.com/chat/completions", headers={"Authorization": f"Bearer {api_key}"}, json=payload)
        response.raise_for_status(); data = response.json()
    content = data["choices"][0]["message"]["content"]
    result = json.loads(content)
    if not result.get("title") or not result.get("body_html"): raise ValueError("DeepSeek вернул неполный черновик")
    result["image_url"] = result.get("image_url") or None
    return result
