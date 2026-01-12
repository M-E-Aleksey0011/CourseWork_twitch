# services/app_state.py
from __future__ import annotations

import random
from typing import List, Optional, Dict, Any

from twitchAPI.chat import Chat
from twitchAPI.twitch import Twitch
from openai import OpenAI


class AppState:
    """
    Глобальное состояние приложения.
    Используется всеми сервисами (Telegram / Twitch / AI).
    """

    def __init__(self):
        # ==================================================
        # CONFIG
        # ==================================================
        self.APP_ID: Optional[str] = None
        self.APP_SECRET: Optional[str] = None
        self.TELEGRAM_API_KEY: Optional[str] = None

        # ==================================================
        # ADMINS / ROLES
        # ==================================================
        # список админов:
        # [{ telegram_id, username, role }]
        self.ADMINS: List[Dict[str, Any]] = []

        # текущий активный админ (устанавливается при /start)
        self.ACTIVE_TELEGRAM_ID: Optional[int] = None
        self.ACTIVE_ROLE: Optional[str] = None  # owner / admin

        # ==================================================
        # DEEPSEEK / AI
        # ==================================================
        self.DEEPSEEK_KEYS: List[str] = []
        self.client: Optional[OpenAI] = None
        self.current_key_index: int = 0

        # ==================================================
        # STOP WORDS
        # ==================================================
        self.STOP_WORDS: List[str] = []
        self.STOP_WORDS_MODE: bool = False

        # ==================================================
        # TWITCH
        # ==================================================
        self.CURRENT_CHANNEL: Optional[str] = None
        self.TARGET_CHANNEL: Optional[str] = None

        self.twitch_app: Optional[Twitch] = None
        self.chat: Optional[Chat] = None

        # ==================================================
        # TELEGRAM
        # ==================================================
        self.telegram_bot = None          # aiogram.Bot
        self.TELEGRAM_LOOP = None         # asyncio loop

        # ==================================================
        # BOT MODES / FLAGS
        # ==================================================
        self.BOT_ENABLED: bool = False

        self.CHANGE_CHANNEL_MODE: bool = False
        self.ADDING_KEY_MODE: bool = False
        self.DELETING_KEY_MODE: bool = False

        # ==================================================
        # CHAT MEMORY / TRIGGERS
        # ==================================================
        self.chat_history: List[str] = []
        self.trigger_messages: List[str] = []
        self.message_threshold: int = random.randint(7, 12)

        # ==================================================
        # DECORATION WORDS
        # ==================================================
        self.words: List[str] = [
            "<3", "PoroSad", "WhySoSerious", "BangbooBounce", "SUBprise",
            "BloodTrail", "DinoDance", "CoolCat", "BabyRage", "ItsBoshyTime",
            "NotLikeThis",
            " ", " ", " ", " ", " ", " ", " ", " ", " ", " ", " "
        ]

    # ==================================================
    # HELPERS
    # ==================================================

    def is_admin(self, telegram_id: int) -> bool:
        """Проверяет, является ли пользователь админом."""
        return any(a["telegram_id"] == telegram_id for a in self.ADMINS)

    def get_admin_role(self, telegram_id: int) -> Optional[str]:
        """Возвращает роль админа (owner/admin) или None."""
        for a in self.ADMINS:
            if a["telegram_id"] == telegram_id:
                return a.get("role")
        return None

    def get_main_admin_id(self) -> Optional[int]:
        """
        Возвращает telegram_id owner-а, если есть,
        иначе — первого админа.
        """
        for a in self.ADMINS:
            if a.get("role") == "owner":
                return a["telegram_id"]
        return self.ADMINS[0]["telegram_id"] if self.ADMINS else None

    def set_active_admin(self, telegram_id: int):
        """Устанавливает активного админа для текущей сессии."""
        self.ACTIVE_TELEGRAM_ID = telegram_id
        self.ACTIVE_ROLE = self.get_admin_role(telegram_id)

    def reset_triggers(self):
        """Сбрасывает накопленные сообщения и триггеры."""
        self.chat_history.clear()
        self.trigger_messages.clear()
        self.message_threshold = random.randint(7, 12)


# ======================================================
# GLOBAL STATE
# ======================================================

state = AppState()
