# database/db.py
import sqlite3
from pathlib import Path

DB_PATH = Path("bot.db")


def get_db_connection():
    """Подключение к SQLite-базе."""
    return sqlite3.connect(DB_PATH)
