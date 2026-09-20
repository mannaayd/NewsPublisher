from pathlib import Path
import aiosqlite


class Database:
    def __init__(self, path: str):
        self.path = path
        self.db: aiosqlite.Connection | None = None

    async def connect(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.path)
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript("""
        CREATE TABLE IF NOT EXISTS news (
          id INTEGER PRIMARY KEY AUTOINCREMENT, guid TEXT UNIQUE NOT NULL,
          url TEXT NOT NULL, title TEXT NOT NULL, description TEXT,
          published_at TEXT, image_url TEXT, status TEXT NOT NULL DEFAULT 'new',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS drafts (
          id INTEGER PRIMARY KEY AUTOINCREMENT, news_id INTEGER NOT NULL,
          title TEXT NOT NULL, body_html TEXT NOT NULL, image_url TEXT,
          source_url TEXT NOT NULL, model TEXT, status TEXT NOT NULL DEFAULT 'draft',
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY(news_id) REFERENCES news(id)
        );
        CREATE TABLE IF NOT EXISTS publications (
          id INTEGER PRIMARY KEY AUTOINCREMENT, draft_id INTEGER NOT NULL,
          chat_id TEXT NOT NULL, message_id INTEGER NOT NULL, published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY, value TEXT NOT NULL
        );
        """)
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    async def add_news(self, item: dict) -> bool:
        try:
            await self.db.execute("INSERT INTO news(guid,url,title,description,published_at,image_url) VALUES(?,?,?,?,?,?)", tuple(item.get(k) for k in ("guid", "url", "title", "description", "published_at", "image_url")))
            await self.db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def list_news(self, limit=10, offset=0):
        cur = await self.db.execute("SELECT * FROM news WHERE status='new' ORDER BY COALESCE(published_at, created_at) DESC LIMIT ? OFFSET ?", (limit, offset))
        return await cur.fetchall()

    async def get_news(self, news_id):
        cur = await self.db.execute("SELECT * FROM news WHERE id=?", (news_id,))
        return await cur.fetchone()

    async def set_news_status(self, news_id, status):
        await self.db.execute("UPDATE news SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, news_id)); await self.db.commit()

    async def save_article(self, news_id, text, html):
        await self.db.execute("INSERT INTO articles(news_id,article_text,article_html) VALUES(?,?,?)", (news_id, text, html)); await self.db.commit()

    async def get_article(self, news_id):
        cur = await self.db.execute("SELECT * FROM articles WHERE news_id=? ORDER BY id DESC LIMIT 1", (news_id,)); return await cur.fetchone()

    async def add_draft(self, news_id, title, body_html, image_url, source_url, model):
        cur = await self.db.execute("INSERT INTO drafts(news_id,title,body_html,image_url,source_url,model) VALUES(?,?,?,?,?,?)", (news_id,title,body_html,image_url,source_url,model)); await self.db.commit(); return cur.lastrowid

    async def get_draft(self, draft_id):
        cur = await self.db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)); return await cur.fetchone()

    async def update_draft(self, draft_id, body_html):
        await self.db.execute("UPDATE drafts SET body_html=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (body_html,draft_id)); await self.db.commit()

    async def update_draft_content(self, draft_id, title, body_html, image_url=None):
        await self.db.execute("UPDATE drafts SET title=?,body_html=?,image_url=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (title, body_html, image_url, draft_id)); await self.db.commit()

    async def delete_draft(self, draft_id):
        await self.db.execute("DELETE FROM drafts WHERE id=? AND status='draft'", (draft_id,)); await self.db.commit()

    async def get_setting(self, key, default=None):
        cur = await self.db.execute("SELECT value FROM settings WHERE key=?", (key,)); row = await cur.fetchone()
        return row["value"] if row else default

    async def set_setting(self, key, value):
        await self.db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value)); await self.db.commit()

    async def mark_published(self, draft_id, chat_id, message_id):
        await self.db.execute("UPDATE drafts SET status='published',updated_at=CURRENT_TIMESTAMP WHERE id=?", (draft_id,))
        await self.db.execute("INSERT INTO publications(draft_id,chat_id,message_id) VALUES(?,?,?)", (draft_id,str(chat_id),message_id)); await self.db.commit()
