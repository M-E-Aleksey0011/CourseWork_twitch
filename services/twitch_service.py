# services/twitch_service.py
import asyncio
from twitchAPI.chat import Chat, ChatMessage, EventData
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.twitch import Twitch

from services.app_state import state
from services.ai_service import (
    init_ai_client,
    get_first_working_key,
    switch_to_next_key,
    send_ai_message,
)
from database.repository import load_deepseek_keys


# ======================================================
# TWITCH CHAT HANDLERS
# ======================================================

async def on_message(msg: ChatMessage):
    """
    Обработчик сообщений Twitch-чата.
    """
    # режимы паузы (настройки из Telegram)
    if (
        state.CHANGE_CHANNEL_MODE
        or state.ADDING_KEY_MODE
        or state.DELETING_KEY_MODE
        or state.STOP_WORDS_MODE
    ):
        print(f"[PAUSED] {msg.user.display_name}: {msg.text}")
        return

    text_lower = msg.text.lower()

    # стоп-слова (обращения к стримеру и т.п.)
    for w in state.STOP_WORDS:
        if w in text_lower:
            print(f"[STOP WORD] {msg.user.display_name}: {msg.text}")
            return

    print(f"{msg.user.display_name}: {msg.text}")

    # пересылка админу в Telegram (только если бот включён)
    if state.BOT_ENABLED:
        try:
            from asyncio import run_coroutine_threadsafe
            admin_id = state.get_main_admin_id()
            if (
                state.TELEGRAM_LOOP
                and state.telegram_bot
                and admin_id
            ):
                run_coroutine_threadsafe(
                    state.telegram_bot.send_message(
                        admin_id,
                        f"{msg.user.display_name}: {msg.text}"
                    ),
                    state.TELEGRAM_LOOP
                )
        except Exception as e:
            print("⚠ Ошибка пересылки сообщения в Telegram:", e)

    # история для AI
    state.chat_history.append(f"{msg.user.display_name}: {msg.text}")
    if len(state.chat_history) > 7:
        state.chat_history.pop(0)

    state.trigger_messages.append(msg.text)

    await send_ai_message()


async def on_ready(event: EventData):
    await event.chat.join_room(state.CURRENT_CHANNEL)
    print(f"🎮 Twitch-бот подключён к каналу #{state.CURRENT_CHANNEL}")


# ======================================================
# TWITCH INIT
# ======================================================

async def init_twitch_bot():
    """
    Инициализация Twitch-бота.
    Вызывается один раз после того, как админ вошёл (/start).
    """
    if state.chat is not None:
        # уже инициализирован
        return

    if not state.ACTIVE_TELEGRAM_ID:
        print("⚠ Нельзя инициализировать Twitch без активного админа.")
        return

    # ==================================================
    # DEEPSEEK KEYS
    # ==================================================
    state.DEEPSEEK_KEYS = load_deepseek_keys(state.ACTIVE_TELEGRAM_ID)

    if not state.DEEPSEEK_KEYS:
        print("❌ У админа нет DeepSeek ключей.")
        return

    working_key = get_first_working_key()
    if not working_key:
        print("❌ Ни один DeepSeek ключ не работает.")
        return

    # инициализация AI клиента
    if not init_ai_client():
        return

    # ==================================================
    # TWITCH AUTH
    # ==================================================
    if not state.APP_ID or not state.APP_SECRET:
        print("❌ Не заданы Twitch APP_ID / APP_SECRET.")
        return

    state.twitch_app = await Twitch(state.APP_ID, state.APP_SECRET)

    auth = UserAuthenticator(
        state.twitch_app,
        [
            AuthScope.CHAT_READ,
            AuthScope.CHAT_EDIT,
            AuthScope.CHANNEL_MANAGE_BROADCAST,
        ],
    )

    token, refresh_token = await auth.authenticate()

    await state.twitch_app.set_user_authentication(
        token,
        [
            AuthScope.CHAT_READ,
            AuthScope.CHAT_EDIT,
            AuthScope.CHANNEL_MANAGE_BROADCAST,
        ],
        refresh_token,
    )

    # ==================================================
    # CHAT
    # ==================================================
    state.chat = await Chat(state.twitch_app)

    state.chat.register_event(ChatEvent.READY, on_ready)
    state.chat.register_event(ChatEvent.MESSAGE, on_message)

    state.chat.start()

    print("✅ Twitch-чат запущен (бот отвечает только когда BOT_ENABLED = True)")
