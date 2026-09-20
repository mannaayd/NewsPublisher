from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_channel_id: str
    admin_telegram_ids: str
    rss_feed_url: str
    scrapit_base_url: str = "http://127.0.0.1:7331"
    deepseek_api_key: str
    deepseek_model: str = "deepseek-chat"
    subscribe_url: str = "https://t.me/"
    database_url: str = "./data/news.db"
    rss_poll_interval_seconds: int = 600
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def admin_ids(self) -> set[int]:
        return {int(value.strip()) for value in self.admin_telegram_ids.split(",") if value.strip()}
