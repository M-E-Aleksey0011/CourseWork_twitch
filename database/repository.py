# database/repository.py
from __future__ import annotations

from typing import Optional, List, Dict, Any
from .db import get_db_connection


# ======================================================
# CONFIG
# ======================================================

def load_config_from_db() -> Dict[str, str]:
    """
    Загружаем client_id, client_secret и telegram_api_key из таблицы config.
    Возвращает dict, где ключи — это 'key' из таблицы config.
    """
    cfg: Dict[str, str] = {}
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM config")
        rows = cur.fetchall()
        cfg = {str(k): str(v) for k, v in rows if k is not None and v is not None}
    except Exception as e:
        print("⚠ Ошибка загрузки конфигурации из БД:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass
    return cfg


# ======================================================
# ADMINS / ROLES
# ======================================================

def load_admins() -> List[Dict[str, Any]]:
    """
    Возвращает список админов:
    [
        {"telegram_id": int, "username": str|None, "role": str}
    ]
    """
    admins: List[Dict[str, Any]] = []
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT telegram_id, username, role FROM admins")
        rows = cur.fetchall()
        admins = [
            {"telegram_id": int(r[0]), "username": r[1], "role": r[2]}
            for r in rows
            if r and r[0] is not None
        ]
    except Exception as e:
        print("⚠ Ошибка загрузки админов:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass
    return admins


def get_admin_role(telegram_id: int) -> Optional[str]:
    """Возвращает роль админа (owner/admin) или None."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT role FROM admins WHERE telegram_id = ?", (telegram_id,))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception as e:
        print("⚠ Ошибка получения роли админа:", e)
        return None
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


# ======================================================
# DEEPSEEK KEYS (Admin+ / per-owner)
# ======================================================

def load_deepseek_keys(owner_telegram_id: int) -> List[str]:
    """
    Возвращает активные и валидные DeepSeek-ключи,
    принадлежащие конкретному админу.
    """
    keys: List[str] = []
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT key
            FROM deepseek_keys
            WHERE is_active = 1
              AND is_valid = 1
              AND owner_telegram_id = ?
            ORDER BY id
            """,
            (owner_telegram_id,),
        )
        rows = cur.fetchall()
        keys = [r[0] for r in rows if r and r[0]]
    except Exception as e:
        print("⚠ Не удалось загрузить ключи DeepSeek:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass
    return keys


def add_deepseek_key_to_db(key: str, owner_telegram_id: int) -> None:
    """Добавляет новый DeepSeek-ключ конкретному админу."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO deepseek_keys (key, is_active, is_valid, owner_telegram_id)
            VALUES (?, 1, 1, ?)
            """,
            (key, owner_telegram_id),
        )
        conn.commit()
    except Exception as e:
        print("⚠ Не удалось сохранить ключ в БД:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


def delete_deepseek_key_from_db(key: str, owner_telegram_id: int) -> None:
    """Удаляет DeepSeek-ключ конкретного админа."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            DELETE FROM deepseek_keys
            WHERE key = ?
              AND owner_telegram_id = ?
            """,
            (key, owner_telegram_id),
        )
        conn.commit()
    except Exception as e:
        print("⚠ Не удалось удалить ключ из БД:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


# ======================================================
# CHANNELS / BOT STATE (per-owner)
# ======================================================

def load_bot_state(owner_telegram_id: int):
    """
    Возвращает (channel_name, bot_enabled) для конкретного админа.
    Если данных нет — (None, False).
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT c.name, b.bot_enabled
            FROM bot_state b
            LEFT JOIN channels c ON b.current_channel_id = c.id
            WHERE b.owner_telegram_id = ?
            """,
            (owner_telegram_id,),
        )
        row = cur.fetchone()
        if row:
            return row[0], bool(row[1])
    except Exception as e:
        print("⚠ Не удалось загрузить состояние бота:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass
    return None, False


def set_current_channel_in_db(channel_name: str, owner_telegram_id: int) -> None:
    """
    Устанавливает текущий Twitch-канал для конкретного админа.
    channels: хранит каналы владельца
    bot_state: хранит активный канал владельца
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 1) Канал гарантированно существует
        cur.execute(
            """
            INSERT OR IGNORE INTO channels (name, is_active, owner_telegram_id)
            VALUES (?, 0, ?)
            """,
            (channel_name, owner_telegram_id),
        )

        # 2) Снять активность со всех каналов владельца
        cur.execute(
            """
            UPDATE channels
            SET is_active = 0
            WHERE owner_telegram_id = ?
            """,
            (owner_telegram_id,),
        )

        # 3) Сделать активным нужный
        cur.execute(
            """
            UPDATE channels
            SET is_active = 1
            WHERE name = ?
              AND owner_telegram_id = ?
            """,
            (channel_name, owner_telegram_id),
        )

        # 4) bot_state строка владельца должна быть
        cur.execute(
            """
            INSERT OR IGNORE INTO bot_state (owner_telegram_id, bot_enabled, current_channel_id)
            VALUES (?, 0, NULL)
            """,
            (owner_telegram_id,),
        )

        # 5) Проставить current_channel_id
        cur.execute(
            """
            UPDATE bot_state
            SET current_channel_id = (
                SELECT id
                FROM channels
                WHERE name = ?
                  AND owner_telegram_id = ?
                LIMIT 1
            )
            WHERE owner_telegram_id = ?
            """,
            (channel_name, owner_telegram_id, owner_telegram_id),
        )

        conn.commit()
    except Exception as e:
        print("⚠ Не удалось обновить канал в БД:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


# ======================================================
# STOP WORDS (GLOBAL)
# ======================================================

def load_stop_words() -> List[str]:
    """Возвращает список стоп-слов из таблицы stop_words."""
    words: List[str] = []
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT word FROM stop_words ORDER BY id")
        rows = cur.fetchall()
        words = [r[0].lower() for r in rows if r and r[0]]
    except Exception as e:
        print("⚠ Не удалось загрузить стоп-слова:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass
    return words


def add_stop_word(word: str) -> None:
    """Добавляет стоп-слово в БД."""
    w = word.lower().strip()
    if not w:
        return
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO stop_words (word) VALUES (?)", (w,))
        conn.commit()
    except Exception as e:
        print("⚠ Не удалось добавить стоп-слово:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


def delete_stop_word(word: str) -> None:
    """Удаляет стоп-слово из БД."""
    w = word.lower().strip()
    if not w:
        return
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM stop_words WHERE word = ?", (w,))
        conn.commit()
    except Exception as e:
        print("⚠ Не удалось удалить стоп-слово:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


# ======================================================
# FREE SESSION USERS (current run only)
# ======================================================

def clear_free_session_users() -> None:
    """
    Очищает таблицу free_session_users.
    Вызывается один раз при старте программы.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM free_session_users")
        conn.commit()
    except Exception as e:
        print("⚠ Ошибка очистки free_session_users:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


def register_free_user(telegram_id: int, username: Optional[str], first_name: Optional[str]) -> None:
    """
    Регистрирует free пользователя в текущей сессии.
    Если уже есть — ничего не делает.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO free_session_users (telegram_id, username, first_name)
            VALUES (?, ?, ?)
            """,
            (telegram_id, username, first_name),
        )
        conn.commit()
    except Exception as e:
        print("⚠ Ошибка регистрации free пользователя:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


def increment_free_messages(telegram_id: int) -> None:
    """Увеличивает счётчик сообщений free пользователя."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE free_session_users
            SET messages_count = messages_count + 1
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        conn.commit()
    except Exception as e:
        print("⚠ Ошибка увеличения счётчика сообщений:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


def is_free_user_banned(telegram_id: int) -> bool:
    """Проверяет, забанен ли free пользователь в рамках текущей сессии."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT is_banned
            FROM free_session_users
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        row = cur.fetchone()
        return bool(row[0]) if row else False
    except Exception as e:
        print("⚠ Ошибка проверки бана free пользователя:", e)
        return False
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


def ban_free_user(telegram_id: int) -> None:
    """Банит free пользователя в рамках текущей сессии."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE free_session_users
            SET is_banned = 1
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        conn.commit()
    except Exception as e:
        print("⚠ Ошибка бана free пользователя:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass


def get_free_users() -> List[Dict[str, Any]]:
    """Возвращает список всех free пользователей текущей сессии."""
    users: List[Dict[str, Any]] = []
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT telegram_id, username, first_name, messages_count, is_banned, created_at
            FROM free_session_users
            ORDER BY messages_count DESC
            """
        )
        rows = cur.fetchall()
        users = [
            {
                "telegram_id": r[0],
                "username": r[1],
                "first_name": r[2],
                "messages_count": r[3],
                "is_banned": bool(r[4]),
                "created_at": r[5],
            }
            for r in rows
            if r and r[0] is not None
        ]
    except Exception as e:
        print("⚠ Ошибка получения списка free пользователей:", e)
    finally:
        try:
            if conn:
                conn.close()
        except:
            pass
    return users
