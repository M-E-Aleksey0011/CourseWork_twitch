# services/telegram_service.py
from aiogram import Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from services.app_state import state
from database.repository import (
    load_deepseek_keys,
    add_deepseek_key_to_db,
    delete_deepseek_key_from_db,
    load_stop_words,
    add_stop_word,
    delete_stop_word,
    set_current_channel_in_db,
    load_bot_state,
)


# ======================================================
# KEYBOARDS
# ======================================================

main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🚀 Запустить бота"),
            KeyboardButton(text="⛔ Остановить бота"),
        ],
        [
            KeyboardButton(text="🔄 Сменить канал"),
            KeyboardButton(text="➕ Добавить ключ DeepSeek"),
        ],
        [
            KeyboardButton(text="🔑 Наши ключи"),
            KeyboardButton(text="🛑 Стоп-слова"),
        ],
    ],
    resize_keyboard=True,
)


# ======================================================
# START / AUTH
# ======================================================

async def cmd_start(message: types.Message):
    telegram_id = message.from_user.id

    if not state.is_admin(telegram_id):
        await message.answer(
            "Этот бот служебный.\n"
            "У тебя нет прав администратора."
        )
        return

    # фиксируем активного админа
    state.set_active_admin(telegram_id)

    # загружаем персональные данные админа
    state.DEEPSEEK_KEYS = load_deepseek_keys(telegram_id)
    state.STOP_WORDS = load_stop_words()

    channel, enabled = load_bot_state(telegram_id)
    if channel:
        state.CURRENT_CHANNEL = channel
        state.TARGET_CHANNEL = channel
    state.BOT_ENABLED = enabled

    await message.answer(
        "👋 Привет!\n\n"
        "Ты вошёл в панель управления Twitch-ботом.\n\n"
        "Доступные действия:\n"
        "🚀 Запустить бота\n"
        "⛔ Остановить бота\n"
        "🔄 Сменить канал\n"
        "➕ Добавить ключ DeepSeek\n"
        "🔑 Наши ключи\n"
        "🛑 Стоп-слова",
        reply_markup=main_kb
    )


# ======================================================
# BOT ENABLE / DISABLE
# ======================================================

async def cmd_enable(message: types.Message):
    if not state.is_admin(message.from_user.id):
        return

    state.BOT_ENABLED = True
    state.reset_triggers()

    state.CHANGE_CHANNEL_MODE = False
    state.ADDING_KEY_MODE = False
    state.DELETING_KEY_MODE = False
    state.STOP_WORDS_MODE = False

    await message.answer("✅ Бот включён. Теперь он отвечает в Twitch-чате.")


async def cmd_disable(message: types.Message):
    if not state.is_admin(message.from_user.id):
        return

    state.BOT_ENABLED = False
    state.reset_triggers()

    state.CHANGE_CHANNEL_MODE = False
    state.ADDING_KEY_MODE = False
    state.DELETING_KEY_MODE = False
    state.STOP_WORDS_MODE = False

    await message.answer("⛔ Бот остановлен.")


# ======================================================
# CHANGE CHANNEL
# ======================================================

async def cmd_change_channel(message: types.Message):
    if not state.is_admin(message.from_user.id):
        return

    state.BOT_ENABLED = False
    state.reset_triggers()

    state.CHANGE_CHANNEL_MODE = True
    state.ADDING_KEY_MODE = False
    state.DELETING_KEY_MODE = False
    state.STOP_WORDS_MODE = False

    await message.answer(
        "🔄 Смена Twitch-канала.\n\n"
        "Введи название канала (без @ и ссылок)."
    )


# ======================================================
# DEEPSEEK KEYS
# ======================================================

async def cmd_add_key(message: types.Message):
    if not state.is_admin(message.from_user.id):
        return

    state.BOT_ENABLED = False
    state.reset_triggers()

    state.ADDING_KEY_MODE = True
    state.CHANGE_CHANNEL_MODE = False
    state.DELETING_KEY_MODE = False
    state.STOP_WORDS_MODE = False

    await message.answer(
        "➕ Добавление DeepSeek-ключа.\n\n"
        "Отправь новый API-ключ целиком.\n"
        "Отправь 0 — для отмены."
    )


async def cmd_show_keys(message: types.Message):
    if not state.is_admin(message.from_user.id):
        return

    state.BOT_ENABLED = False
    state.reset_triggers()

    state.DELETING_KEY_MODE = True
    state.ADDING_KEY_MODE = False
    state.CHANGE_CHANNEL_MODE = False
    state.STOP_WORDS_MODE = False

    if not state.DEEPSEEK_KEYS:
        await message.answer("🔑 Список ключей пуст.")
        return

    text = "🔑 Твои DeepSeek-ключи:\n\n"
    for i, key in enumerate(state.DEEPSEEK_KEYS, 1):
        short = key[:12] + "..." if len(key) > 12 else key
        text += f"{i}) {short}\n"

    text += "\nОтправь номер ключа — удалить\n0 — отмена"

    await message.answer(text)


# ======================================================
# STOP WORDS
# ======================================================

async def cmd_stop_words(message: types.Message):
    if not state.is_admin(message.from_user.id):
        return

    state.BOT_ENABLED = False
    state.reset_triggers()

    state.STOP_WORDS_MODE = True
    state.CHANGE_CHANNEL_MODE = False
    state.ADDING_KEY_MODE = False
    state.DELETING_KEY_MODE = False

    state.STOP_WORDS = load_stop_words()

    if not state.STOP_WORDS:
        await message.answer(
            "🛑 Стоп-слов пока нет.\n\n"
            "Отправь слово или фразу — добавить.\n"
            "0 — выход."
        )
        return

    text = "🛑 Текущие стоп-слова:\n\n"
    for i, w in enumerate(state.STOP_WORDS, 1):
        text += f"{i}) {w}\n"

    text += "\nОтправь слово — добавить\nНомер — удалить\n0 — выход"

    await message.answer(text)


# ======================================================
# TEXT HANDLER (MODES)
# ======================================================

async def handle_text(message: types.Message):
    if not state.is_admin(message.from_user.id):
        return

    text = message.text.strip()
    owner_id = state.ACTIVE_TELEGRAM_ID

    # ---------- CHANGE CHANNEL ----------
    if state.CHANGE_CHANNEL_MODE:
        if not text:
            await message.answer("❌ Название канала не может быть пустым.")
            return

        channel = text.lstrip("@").lower()
        state.CURRENT_CHANNEL = channel
        state.TARGET_CHANNEL = channel

        set_current_channel_in_db(channel, owner_id)

        state.CHANGE_CHANNEL_MODE = False

        await message.answer(
            f"✅ Канал установлен: `{channel}`\n\n"
            "Бот сейчас выключен.\n"
            "Нажми «🚀 Запустить бота».",
            parse_mode="Markdown",
            reply_markup=main_kb
        )
        return

    # ---------- ADD KEY ----------
    if state.ADDING_KEY_MODE:
        if text == "0":
            state.ADDING_KEY_MODE = False
            await message.answer("❎ Добавление ключа отменено.")
            return

        add_deepseek_key_to_db(text, owner_id)
        state.DEEPSEEK_KEYS.append(text)

        state.ADDING_KEY_MODE = False

        await message.answer("✅ Ключ добавлен.")
        return

    # ---------- DELETE KEY ----------
    if state.DELETING_KEY_MODE:
        if text == "0":
            state.DELETING_KEY_MODE = False
            await message.answer("❎ Удаление отменено.")
            return

        if not text.isdigit():
            await message.answer("❌ Введи номер ключа.")
            return

        idx = int(text)
        if idx < 1 or idx > len(state.DEEPSEEK_KEYS):
            await message.answer("❌ Неверный номер.")
            return

        key = state.DEEPSEEK_KEYS.pop(idx - 1)
        delete_deepseek_key_from_db(key, owner_id)

        state.DELETING_KEY_MODE = False
        await message.answer("🗑 Ключ удалён.")
        return

    # ---------- STOP WORDS ----------
    if state.STOP_WORDS_MODE:
        if text == "0":
            state.STOP_WORDS_MODE = False
            await message.answer("Выход из управления стоп-словами.")
            return

        if text.isdigit():
            idx = int(text)
            if 1 <= idx <= len(state.STOP_WORDS):
                word = state.STOP_WORDS.pop(idx - 1)
                delete_stop_word(word)
                await message.answer(f"❌ Удалено: {word}")
            else:
                await message.answer("❌ Неверный номер.")
            return

        add_stop_word(text)
        state.STOP_WORDS.append(text.lower())
        await message.answer(f"✅ Добавлено: {text.lower()}")
        return


# ======================================================
# REGISTER
# ======================================================

def register_handlers(dp: Dispatcher):
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_enable, F.text == "🚀 Запустить бота")
    dp.message.register(cmd_disable, F.text == "⛔ Остановить бота")
    dp.message.register(cmd_change_channel, F.text == "🔄 Сменить канал")
    dp.message.register(cmd_add_key, F.text == "➕ Добавить ключ DeepSeek")
    dp.message.register(cmd_show_keys, F.text == "🔑 Наши ключи")
    dp.message.register(cmd_stop_words, F.text == "🛑 Стоп-слова")
    dp.message.register(handle_text)
