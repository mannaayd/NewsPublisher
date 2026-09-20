import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.config import Settings
from app.db.database import Database
from app.services.scrapit import extract
from app.services.deepseek import generate
from app.bot.handlers import router_for
from app.services.rss import fetch

logging.basicConfig(level=logging.INFO)

async def poll_rss(settings, db):
    while True:
        try:
            for item in await fetch(settings.rss_feed_url): await db.add_news(item)
        except Exception: logging.exception("RSS update failed")
        await asyncio.sleep(settings.rss_poll_interval_seconds)

async def main():
    settings = Settings()
    db = Database(settings.database_url); await db.connect()
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router_for(settings, db, lambda url: extract(settings.scrapit_base_url, url), lambda title, text, url: generate(settings.deepseek_api_key, settings.deepseek_model, title, text, url)))
    poller = asyncio.create_task(poll_rss(settings, db))
    try: await dp.start_polling(bot)
    finally: poller.cancel(); await db.close(); await bot.session.close()

if __name__ == "__main__": asyncio.run(main())
