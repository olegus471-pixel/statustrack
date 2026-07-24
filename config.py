import os
from dataclasses import dataclass


@dataclass
class Settings:
    bot_token: str
    db_path: str
    check_hour_utc: int   # hour of day (UTC) to run the daily check, 0-23
    check_minute_utc: int
    request_timeout: int


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "BOT_TOKEN is not set. Export it or put it in a .env file, e.g.:\n"
            "  export BOT_TOKEN=123456:ABC-DEF...\n"
        )
    return Settings(
        bot_token=token,
        db_path=os.getenv("DB_PATH", "aima_bot.sqlite3"),
        check_hour_utc=int(os.getenv("CHECK_HOUR_UTC", "8")),
        check_minute_utc=int(os.getenv("CHECK_MINUTE_UTC", "0")),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "15")),
    )
