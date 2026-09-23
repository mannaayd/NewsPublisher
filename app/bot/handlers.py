from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from html import escape
import re
from app.services import deepseek as deepseek_service
from app.services.images import download_image
from aiogram.types import FSInputFile

class EditState(StatesGroup):
    body = State()
    prompt = State()
    rewrite_prompt = State()

def clean_html(value: str) -> str:
    value = re.sub(r"</?p\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<(?!/?(?:b|strong|i|em|u|s|a|code)(?:\s|>|/))[^>]+>", "", value, flags=re.I)
    value = re.sub(r"<(a)([^>]+)>", lambda m: m.group(0) if re.search(r'href=["\']https?://', m.group(0), re.I) else "", value, flags=re.I)
    return value[:4090]

def router_for(settings, db, scrapit, deepseek):
    router = Router()
    def allowed(user_id): return user_id in settings.admin_ids
    def menu(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📰 Новые новости", callback_data="news:0")],[InlineKeyboardButton(text="🔄 Обновить RSS", callback_data="rss")],[InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")]])
    @router.message(CommandStart())
    async def start(message: Message):
        if not allowed(message.from_user.id): return await message.answer("У вас нет доступа к этому боту.")
        await message.answer("Панель управления новостями", reply_markup=menu())
    @router.message(Command("news"))
    async def news_command(message: Message):
        if not allowed(message.from_user.id): return await message.answer("У вас нет доступа к этому боту.")
        rows = await db.list_news(5, 0)
        if not rows: return await message.answer("Новых новостей нет.", reply_markup=menu())
        buttons = [[InlineKeyboardButton(text=f"Выбрать: {row['title'][:35]}", callback_data=f"select:{row['id']}")] for row in rows]
        text = "Новые новости:\n\n" + "\n\n".join(f"<b>{escape(row['title'])}</b>" for row in rows)
        await message.answer(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    @router.message(Command("refresh"))
    async def refresh_command(message: Message):
        if not allowed(message.from_user.id): return
        count = 0
        for item in await __import__("app.services.rss", fromlist=["fetch"]).fetch(settings.rss_feed_url): count += await db.add_news(item)
        await message.answer(f"RSS обновлён. Добавлено новостей: {count}", reply_markup=menu())
    @router.message(Command("settings"))
    async def settings_command(message: Message):
        if not allowed(message.from_user.id): return
        await message.answer("Настройки бота", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✏️ Промпт DeepSeek", callback_data="prompt:edit")]]))
    @router.message(Command("cancel"))
    async def cancel_command(message: Message, state: FSMContext):
        if allowed(message.from_user.id): await state.clear(); await message.answer("Действие отменено.", reply_markup=menu())
    @router.callback_query(F.data == "rss")
    async def refresh(call: CallbackQuery):
        if not allowed(call.from_user.id): return
        count = 0
        for item in await __import__("app.services.rss", fromlist=["fetch"]).fetch(settings.rss_feed_url): count += await db.add_news(item)
        await call.answer(f"Добавлено: {count}"); await call.message.edit_text("RSS обновлён", reply_markup=menu())
    @router.callback_query(F.data == "settings")
    async def settings_menu(call: CallbackQuery):
        if not allowed(call.from_user.id): return
        await call.message.edit_text("Настройки бота", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✏️ Промпт DeepSeek", callback_data="prompt:edit")],[InlineKeyboardButton(text="↩️ В меню", callback_data="home")]]))
    @router.callback_query(F.data == "prompt:edit")
    async def prompt_edit(call: CallbackQuery, state: FSMContext):
        if not allowed(call.from_user.id): return
        prompt = await db.get_setting("deepseek_prompt", deepseek_service.SYSTEM)
        await state.set_state(EditState.prompt); await call.message.answer(f"Текущий промпт:\n\n{prompt}\n\nПришлите новый промпт одним сообщением.")
    @router.message(EditState.prompt)
    async def prompt_save(message: Message, state: FSMContext):
        if not allowed(message.from_user.id): return
        prompt = (message.text or "").strip()
        if len(prompt) < 50: return await message.answer("Промпт слишком короткий. Пришлите более подробную инструкцию.")
        await db.set_setting("deepseek_prompt", prompt); await state.clear(); await message.answer("✅ Промпт сохранён.", reply_markup=menu())
    @router.callback_query(F.data == "home")
    async def home(call: CallbackQuery):
        if allowed(call.from_user.id): await call.message.edit_text("Панель управления новостями", reply_markup=menu())
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
        row = await db.get_news(int(call.data.split(":")[1]))
        if not row: return await call.answer("Новость не найдена.", show_alert=True)
        if row["status"] == "draft":
            existing = await db.get_latest_draft_for_news(row["id"])
            if existing: await call.answer("Для этой новости уже создан черновик."); return await show_draft(call.message, db, existing["id"])
        if row["status"] == "published":
            existing = await db.get_latest_draft_for_news(row["id"])
            if existing:
                publication = await db.get_latest_publication(existing["id"])
                await call.answer("Статья уже публиковалась. Можно опубликовать её снова.")
                return await show_draft(call.message, db, existing["id"], publication)
        if row["status"] in {"extracting", "generating", "extracted", "selected"}:
            return await call.answer("Эта новость уже обрабатывается или была опубликована.", show_alert=True)
        await db.set_news_status(row["id"], "selected"); await call.answer("Извлекаю статью…")
        try:
            article = await scrapit(row["url"]); await db.save_article(row["id"], article["text"], article["html"]); await db.set_news_status(row["id"], "extracted")
            prompt = await db.get_setting("deepseek_prompt", deepseek_service.SYSTEM)
            generated = await deepseek(row["title"], article["text"], row["url"], prompt)
            draft_id = await db.add_draft(row["id"], generated["title"], clean_html(generated["body_html"]), generated.get("image_url") or article.get("image_url") or row["image_url"], row["url"], settings.deepseek_model)
            await db.set_news_status(row["id"], "draft"); await show_draft(call.message, db, draft_id)
        except Exception as exc: await call.message.answer(f"Не удалось подготовить статью: {escape(str(exc))}")
    @router.callback_query(F.data.startswith("skip:"))
    async def skip(call: CallbackQuery):
        if not allowed(call.from_user.id): return
        await db.set_news_status(int(call.data.split(":")[1]), "skipped")
        await call.answer("Новость пропущена")
        await call.message.edit_reply_markup(reply_markup=None)
    async def show_draft(message, db, draft_id, publication=None):
        draft = await db.get_draft(draft_id); text = f"<b>Предпросмотр</b>\n\n{draft['body_html']}\n\n<a href=\"{settings.subscribe_url}\">Новости за бугром. Подписаться.</a>"
        publish_label = "🔁 Опубликовать снова" if publication else "✅ Опубликовать"
        extra = f"\n\nПоследнее сообщение в канале: {publication['message_id']}" if publication else ""
        text += extra
        publish_buttons = [InlineKeyboardButton(text=publish_label, callback_data=f"publish:{draft_id}")]
        if draft["image_url"]: publish_buttons.append(InlineKeyboardButton(text="📝 Без картинки", callback_data=f"publish_mode:text:{draft_id}"))
        publish_buttons.append(InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete:{draft_id}"))
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit:{draft_id}"), InlineKeyboardButton(text="✍️ Переписать с промптом", callback_data=f"rewrite:{draft_id}")], publish_buttons])
        if draft["image_url"]:
            try: await message.answer_photo(draft["image_url"], caption="Изображение для этой статьи")
            except Exception: pass
        await message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=kb)
    @router.callback_query(F.data.startswith("rewrite:"))
    async def rewrite_start(call: CallbackQuery, state: FSMContext):
        if not allowed(call.from_user.id): return
        await state.set_state(EditState.rewrite_prompt); await state.update_data(draft_id=int(call.data.split(":")[1]))
        await call.message.answer("Пришлите дополнительный промпт для переписывания. Например: «Сделай текст короче и добавь больше контекста».")
    @router.message(EditState.rewrite_prompt)
    async def rewrite_apply(message: Message, state: FSMContext):
        if not allowed(message.from_user.id): return
        data = await state.get_data(); draft = await db.get_draft(data["draft_id"]); article = await db.get_article(draft["news_id"])
        custom_prompt = (message.text or "").strip()
        if not article or not custom_prompt: return await message.answer("Не удалось найти статью или пользовательский промпт пуст.")
        await message.answer("Переписываю пост с вашим промптом…")
        try:
            base = await db.get_setting("deepseek_prompt", deepseek_service.SYSTEM)
            generated = await deepseek(draft["title"], article["article_text"], draft["source_url"], f"{base}\n\nДополнительная инструкция администратора:\n{custom_prompt}")
            await db.update_draft_content(draft["id"], generated["title"], clean_html(generated["body_html"]), generated.get("image_url"))
            await state.clear(); await show_draft(message, db, draft["id"])
        except Exception as exc:
            await state.clear(); await message.answer(f"Не удалось переписать пост: {escape(str(exc))}")
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
        if draft["image_url"] and len(draft["body_html"]) > 900:
            await call.answer("Выберите формат публикации")
            return await call.message.answer("Пост с картинкой ограничен по длине подписи. Выберите вариант:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🖼 С картинкой", callback_data=f"publish_mode:image:{draft['id']}"), InlineKeyboardButton(text="📝 Длинный текст без картинки", callback_data=f"publish_mode:text:{draft['id']}")]]))
        return await publish_draft(call, draft, with_image=bool(draft["image_url"]))

    @router.callback_query(F.data.startswith("publish_mode:"))
    async def publish_mode(call: CallbackQuery):
        if not allowed(call.from_user.id): return
        _, mode, draft_id = call.data.split(":")
        draft = await db.get_draft(int(draft_id))
        await call.answer("Публикую…")
        if mode == "image" and len(draft["body_html"]) > 900:
            article = await db.get_article(draft["news_id"])
            if article:
                base = await db.get_setting("deepseek_prompt", deepseek_service.SYSTEM)
                generated = await deepseek(draft["title"], article["article_text"], draft["source_url"], f"{base}\n\nСделай короткую версию для публикации с изображением. Уложись максимум в 850 символов HTML-текста, сохрани ключевые факты.")
                await db.update_draft_content(draft["id"], generated["title"], clean_html(generated["body_html"]), draft["image_url"])
                draft = await db.get_draft(draft["id"])
        return await publish_draft(call, draft, with_image=mode == "image")

    async def publish_draft(call, draft, with_image):
        post_text = f"{draft['body_html']}\n\n<a href=\"{settings.subscribe_url}\">Новости за бугром. Подписаться.</a>"
        if with_image and draft["image_url"]:
            image_path = await download_image(draft["image_url"], "./data/images", f"draft-{draft['id']}")
            if len(post_text) > 1024:
                return await call.message.answer("Не удалось сократить текст для публикации с изображением. Выберите публикацию без картинки.")
            caption = post_text
            sent = await call.bot.send_photo(settings.telegram_channel_id, FSInputFile(image_path), caption=caption, parse_mode="HTML")
        else:
            if len(post_text) <= 4096:
                sent = await call.bot.send_message(settings.telegram_channel_id, post_text, parse_mode="HTML", disable_web_page_preview=True)
            else:
                sent = await call.bot.send_message(settings.telegram_channel_id, post_text[:4090], parse_mode="HTML", disable_web_page_preview=True)
                await call.bot.send_message(settings.telegram_channel_id, post_text[4090:], parse_mode="HTML", disable_web_page_preview=True)
        await db.mark_published(draft["id"], settings.telegram_channel_id, sent.message_id); await call.message.answer("✅ Опубликовано в канале.")
    return router
