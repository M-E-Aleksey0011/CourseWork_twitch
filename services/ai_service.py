# services/ai_service.py
import random
from typing import Optional
from openai import OpenAI

from .app_state import state


# ======================================================
# DEEPSEEK CLIENT MANAGEMENT
# ======================================================

def init_ai_client() -> bool:
    """
    Инициализирует AI-клиент с первым доступным ключом.
    Возвращает True, если удалось инициализировать.
    """
    if not state.DEEPSEEK_KEYS:
        print("❌ Нет DeepSeek ключей для инициализации.")
        state.client = None
        return False

    state.current_key_index = 0
    key = state.DEEPSEEK_KEYS[state.current_key_index]
    state.client = OpenAI(
        api_key=key,
        base_url="https://openrouter.ai/api/v1"
    )
    print(f"🧠 AI клиент инициализирован: {key[:12]}...")
    return True


def switch_to_next_key() -> bool:
    """
    Переключается на следующий ключ DeepSeek.
    Возвращает False, если ключи закончились.
    """
    state.current_key_index += 1

    if state.current_key_index >= len(state.DEEPSEEK_KEYS):
        print("❌ Все ключи DeepSeek исчерпаны.")
        state.client = None
        return False

    new_key = state.DEEPSEEK_KEYS[state.current_key_index]
    state.client = OpenAI(
        api_key=new_key,
        base_url="https://openrouter.ai/api/v1"
    )
    print(f"🔄 Переключение на новый ключ: {new_key[:12]}...")
    return True


def get_first_working_key(max_retries: int = 3) -> Optional[str]:
    """
    Проверяет ключи и возвращает первый рабочий.
    Используется при старте.
    """
    if not state.DEEPSEEK_KEYS:
        print("❌ Список DeepSeek ключей пуст.")
        return None

    test_prompt = "ответь одним словом: ok"

    for attempt in range(1, max_retries + 1):
        print(f"🔎 Поиск рабочего ключа (попытка {attempt}/{max_retries})")

        for key in state.DEEPSEEK_KEYS:
            try:
                client = OpenAI(
                    api_key=key,
                    base_url="https://openrouter.ai/api/v1"
                )
                response = client.chat.completions.create(
                    model="deepseek/deepseek-r1:free",
                    messages=[
                        {"role": "system", "content": "ответь 'ok'"},
                        {"role": "user", "content": test_prompt}
                    ],
                    max_tokens=5
                )
                if response and response.choices:
                    print(f"✅ Рабочий ключ найден: {key[:12]}...")
                    return key
            except Exception as e:
                if "429" in str(e):
                    print(f"⚠ 429 (лимит): {key[:12]}...")
                elif "401" in str(e):
                    print(f"⚠ 401 (невалидный): {key[:12]}...")
                else:
                    print(f"⚠ Ошибка ключа {key[:12]}: {e}")

    print("❌ Не удалось найти рабочий ключ.")
    return None


# ======================================================
# MESSAGE GENERATION
# ======================================================

async def send_ai_message():
    """
    Генерирует и отправляет сообщение в Twitch-чат.
    Вызывается после накопления trigger_messages.
    """
    if not state.BOT_ENABLED:
        return

    if state.client is None:
        print("⚠ AI клиент не инициализирован.")
        return

    if len(state.trigger_messages) < state.message_threshold:
        return

    if not state.chat_history:
        return

    prompt = (
        "Ответь как обычный участник Twitch-чата.\n"
        "Ответ короткий (до 10 слов), без точки в конце, с маленькой буквы.\n\n"
        "История сообщений:\n"
        + "\n".join(state.chat_history)
    )

    for _ in range(len(state.DEEPSEEK_KEYS)):
        try:
            response = state.client.chat.completions.create(
                model="deepseek/deepseek-r1:free",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты обычный зритель Twitch-чата. "
                            "Не притворяйся ботом. Пиши естественно."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                max_tokens=60
            )

            if not response or not response.choices:
                print("⚠ Пустой ответ от AI.")
                return

            message = response.choices[0].message.content
            if not message:
                print("⚠ AI вернул пустое сообщение.")
                return

            # финальное сообщение
            if len(message) > 70:
                sms = random.choice(state.words)
            else:
                sms = message.strip() + " " + random.choice(state.words)

            await state.chat.send_message(state.CURRENT_CHANNEL, sms)
            print(f"🤖 AI → Twitch: {sms}")

            # уведомление админу в Telegram
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
                            f"🤖 Бот отправил в Twitch:\n{sms}"
                        ),
                        state.TELEGRAM_LOOP
                    )
            except Exception as e:
                print("⚠ Ошибка отправки уведомления в Telegram:", e)

            # сброс триггеров
            state.trigger_messages.clear()
            state.message_threshold = random.randint(7, 12)
            return

        except Exception as e:
            err = str(e)
            if "429" in err or "401" in err:
                print("🔁 Проблема с ключом, пробую следующий...")
                if not switch_to_next_key():
                    print("❌ Нет доступных ключей для продолжения.")
                    return
            else:
                print("❌ Ошибка AI:", e)
                return
