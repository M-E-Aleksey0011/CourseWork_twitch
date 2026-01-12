# main.py
import asyncio

from aiogram import Bot as TgBot, Dispatcher

from services.app_state import state
from database.repository import (
    load_config_from_db,
    load_admins,
    load_stop_words,
    clear_free_session_users,
)
from services.telegram_service import register_handlers


async def main():
    print("🚀 main() запущен")

    # ==================================================
    # EVENT LOOP
    # ==================================================
    loop = asyncio.get_running_loop()
    state.TELEGRAM_LOOP = loop

    # ==================================================
    # CLEANUP FREE SESSION (на всякий случай)
    # ==================================================
    clear_free_session_users()

    # ==================================================
    # LOAD CONFIG
    # ==================================================
    cfg = load_config_from_db()
    state.APP_ID = cfg.get("twitch_client_id")
    state.APP_SECRET = cfg.get("twitch_client_secret")
    state.TELEGRAM_API_KEY = cfg.get("telegram_api_key")

    if not state.TELEGRAM_API_KEY:
        print("❌ TELEGRAM_API_KEY не найден в таблице config.")
        return

    # ==================================================
    # LOAD ADMINS
    # ==================================================
    state.ADMINS = load_admins()

    if not state.ADMINS:
        print("⚠ В БД нет администраторов (таблица admins пуста).")

    # ==================================================
    # LOAD STOP WORDS (GLOBAL)
    # ==================================================
    state.STOP_WORDS = load_stop_words()

    # ==================================================
    # TELEGRAM BOT INIT
    # ==================================================
    bot = TgBot(token=state.TELEGRAM_API_KEY)
    dp = Dispatcher()
    state.telegram_bot = bot

    register_handlers(dp)

    print("📲 Telegram-бот запущен и ожидает /start")

    # ==================================================
    # START POLLING
    # ==================================================
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
