from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from html import escape
import re

class EditState(StatesGroup):
    body = State()

def clean_html(value: str) -> str:
    value = re.sub(r"<(?!/?(?:b|strong|i|em|u|s|a|code)(?:\s|>|/))[^>]+>", "", value, flags=re.I)
    value = re.sub(r"<(a)([^>]+)>", lambda m: m.group(0) if re.search(r'href=["\']https?://', m.group(0), re.I) else "", value, flags=re.I)
    return value[:4090]

def router_for(settings, db, scrapit, deepseek):
    router = Router()
    def allowed(user_id): return user_id in settings.admin_ids
    def menu(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📰 Новые новости", callback_data="news:0")],[InlineKeyboardButton(text="🔄 Обновить RSS", callback_data="rss")]])
    @router.message(CommandStart())
    async def start(message: Message):
        if not allowed(message.from_user.id): return await message.answer("У вас нет доступа к этому боту.")
        await message.answer("Панель управления новостями", reply_markup=menu())
    @router.callback_query(F.data == "rss")
    async def refresh(call: CallbackQuery):
        if not allowed(call.from_user.id): return
        count = 0
        for item in await __import__("app.services.rss", fromlist=["fetch"]).fetch(settings.rss_feed_url): count += await db.add_news(item)
        await call.answer(f"Добавлено: {count}"); await call.message.edit_text("RSS обновлён", reply_markup=menu())
    @router.callback_query(F.data.startswith("news:"))
    async def list_news(call: CallbackQuery):
        if not allowed(call.from_user.id): return
        offset = int(call.data.split(":")[1]); rows = await db.list_news(5, offset)
        if not rows: return await call.message.edit_text("Новых новостей нет.", reply_markup=menu())
        buttons = []
        text = "Новые новости:\n\n"
        for row in rows:
            text += f"<b>{escape(row['title'])}</b>\n{escape(row['published_at'] or '')}\n\n"
            buttons.append([InlineKeyboardButton(text=f"Выбрать: {row['title'][:35]}", callback_data=f"select:{row['id']}")])
        buttons.append([InlineKeyboardButton(text="Дальше →", callback_data=f"news:{offset+5}")])
        await call.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    @router.callback_query(F.data.startswith("select:"))
    async def select(call: CallbackQuery):
        if not allowed(call.from_user.id): return
        row = await db.get_news(int(call.data.split(":")[1])); await call.answer("Извлекаю статью…")
        try:
            article = await scrapit(row["url"]); await db.set_news_status(row["id"], "extracted")
            generated = await deepseek(row["title"], article["text"], row["url"])
            draft_id = await db.add_draft(row["id"], generated["title"], generated["body_html"], generated.get("image_url"), row["url"], settings.deepseek_model)
            await db.set_news_status(row["id"], "draft"); await show_draft(call.message, db, draft_id)
        except Exception as exc: await call.message.answer(f"Не удалось подготовить статью: {escape(str(exc))}")
    async def show_draft(message, db, draft_id):
        draft = await db.get_draft(draft_id); text = f"<b>Предпросмотр</b>\n\n{draft['body_html']}\n\n<a href=\"{settings.subscribe_url}\">Новости за кордоном. Подписаться.</a>"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:{draft_id}")],[InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"publish:{draft_id}"),InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{draft_id}")]])
        await message.answer(text, parse_mode="HTML", reply_markup=kb)
    @router.callback_query(F.data.startswith("edit:"))
    async def edit(call: CallbackQuery, state: FSMContext):
        if not allowed(call.from_user.id): return
        await state.set_state(EditState.body); await state.update_data(draft_id=int(call.data.split(":")[1])); await call.message.answer("Пришлите новый текст с Telegram HTML-разметкой.")
    @router.message(EditState.body)
    async def save_edit(message: Message, state: FSMContext):
        if not allowed(message.from_user.id): return
        data = await state.get_data(); await db.update_draft(data["draft_id"], clean_html(message.html_text or escape(message.text or ""))); await state.clear(); await show_draft(message, db, data["draft_id"])
    @router.callback_query(F.data.startswith("delete:"))
    async def delete(call: CallbackQuery):
        if not allowed(call.from_user.id): return
        await db.delete_draft(int(call.data.split(":")[1])); await call.answer("Черновик удалён"); await call.message.edit_text("Черновик удалён.", reply_markup=menu())
    @router.callback_query(F.data.startswith("publish:"))
    async def publish(call: CallbackQuery):
        if not allowed(call.from_user.id): return
        draft = await db.get_draft(int(call.data.split(":")[1]))
        if draft["image_url"]:
            sent = await call.bot.send_photo(settings.telegram_channel_id, draft["image_url"], caption=f"{draft['body_html']}\n\n<a href=\"{settings.subscribe_url}\">Новости за кордоном. Подписаться.</a>", parse_mode="HTML")
        else:
            sent = await call.bot.send_message(settings.telegram_channel_id, f"{draft['body_html']}\n\n<a href=\"{settings.subscribe_url}\">Новости за кордоном. Подписаться.</a>", parse_mode="HTML", disable_web_page_preview=False)
        await db.mark_published(draft["id"], settings.telegram_channel_id, sent.message_id); await call.message.answer("✅ Опубликовано в канале.")
    return router
