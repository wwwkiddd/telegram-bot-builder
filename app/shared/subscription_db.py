import sqlite3
from datetime import datetime, timedelta

DB_FILE = "../backend/subscriptions.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            bot_id TEXT,
            expires_at TEXT
        )''')
        conn.commit()

def set_subscription(user_id: int, bot_id: str, months: int):
    expires = (datetime.utcnow() + timedelta(days=30 * months)).isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("REPLACE INTO subscriptions (user_id, bot_id, expires_at) VALUES (?, ?, ?)",
                  (user_id, bot_id, expires))
        conn.commit()

def get_subscription(user_id: int):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT expires_at FROM subscriptions WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return row[0] if row else None

def get_expired_bots():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT user_id, bot_id FROM subscriptions WHERE expires_at < ?", (datetime.utcnow().isoformat(),))
        return c.fetchall()
