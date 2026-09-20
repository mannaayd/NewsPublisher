# News Channel Bot

Telegram-бот для ручного выбора новостей из RSS SeznamZpravy.cz, извлечения статьи через локальный Scrapit, подготовки поста через DeepSeek и публикации в канале.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

Заполните `.env`: токен бота, ID канала, Telegram ID администратора и ключ DeepSeek.

```bash
python -m app.main
```

Scrapit должен быть доступен по `SCRAPIT_BASE_URL`, обычно `http://127.0.0.1:7331`. Бот должен быть администратором канала с правом публикации сообщений.

## Docker

Scrapit должен быть запущен первым и создать сеть `scrapit_default`. Затем:

```bash
docker compose up -d --build
docker compose logs -f bot
```

Контейнер обращается к Scrapit по внутреннему адресу
`http://scrapit-adapter:7331`; публиковать порт Scrapit в LAN не требуется.

## Поток

RSS обновляется автоматически, но обработка статьи начинается только после ручного выбора новости в боте. После генерации администратор может прислать исправленный текст с Telegram HTML-разметкой и подтвердить публикацию.
