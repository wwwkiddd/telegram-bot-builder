import sqlite3
from datetime import datetime, timedelta

DB_FILE = "../backend/subscriptions.db"

async def set_subscription(bot_id: str, active: bool, paid: bool):
    async with aiosqlite.connect("app/shared/subscriptions.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                bot_id TEXT PRIMARY KEY,
                created_at TEXT,
                active INTEGER,
                paid INTEGER
            )
        """)
        await db.execute("""
            INSERT OR REPLACE INTO subscriptions (bot_id, created_at, active, paid)
            VALUES (?, ?, ?, ?)
        """, (bot_id, datetime.now().isoformat(), int(active), int(paid)))
        await db.commit()

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
