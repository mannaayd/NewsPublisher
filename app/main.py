import asyncio
import logging
import random
from pathlib import Path
import time
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, InlineKeyboardMarkup, InlineKeyboardButton
from html import escape
from app.config import Settings
from app.db.database import Database
from app.services.scrapit import extract
from app.services.deepseek import generate, SYSTEM
from app.bot.handlers import router_for
from app.services.rss import fetch

logging.basicConfig(level=logging.INFO)

HEARTBEAT = Path("/tmp/news-channel-bot.heartbeat")

async def heartbeat():
    while True:
        HEARTBEAT.touch()
        await asyncio.sleep(30)

async def poll_rss(settings, db, bot):
    async def notify(row):
        for admin_id in settings.admin_ids:
            await bot.send_message(admin_id, f"📰 <b>Новая статья</b>\n\n<b>{escape(row['title'])}</b>\n\n<a href=\"{row['url']}\">Открыть статью</a>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Выбрать", callback_data=f"select:{row['id']}"), InlineKeyboardButton(text="Пропустить", callback_data=f"skip:{row['id']}")]]))
        await db.mark_notified(row["id"])
    while True:
        try:
            for item in await fetch(settings.rss_feed_url):
                if await db.add_news(item):
                    row = await db.get_news_by_url(item["url"])
                    if row: await notify(row)
            for row in await db.list_unnotified_news(): await notify(row)
            await db.cleanup_old_articles(days=2)
        except Exception: logging.exception("RSS update failed")
        jitter = random.uniform(-120, 120)
        await asyncio.sleep(max(60, settings.rss_poll_interval_seconds + jitter))

async def main():
    settings = Settings()
    db = Database(settings.database_url); await db.connect()
    bot = Bot(settings.telegram_bot_token)
    await bot.set_my_commands([
        BotCommand(command="start", description="Открыть панель управления"),
        BotCommand(command="news", description="Показать новые новости"),
        BotCommand(command="refresh", description="Обновить RSS"),
        BotCommand(command="settings", description="Настройки бота"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
    ], scope=BotCommandScopeAllPrivateChats())
    dp = Dispatcher()
    dp.include_router(router_for(settings, db, lambda url: extract(settings.scrapit_base_url, url), lambda title, text, url, prompt=None: generate(settings.deepseek_api_key, settings.deepseek_model, title, text, url, prompt)))
    poller = asyncio.create_task(poll_rss(settings, db, bot))
    heartbeat_task = asyncio.create_task(heartbeat())
    try: await dp.start_polling(bot)
    finally: poller.cancel(); heartbeat_task.cancel(); await db.close(); await bot.session.close()

if __name__ == "__main__": asyncio.run(main())
