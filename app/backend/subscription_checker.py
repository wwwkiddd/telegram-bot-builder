import aiosqlite
import asyncio
from datetime import datetime, timedelta
import subprocess
from aiogram import Bot, types
from dotenv import dotenv_values
from pathlib import Path

DB_PATH = "/root/telegram-bot-builder/app/shared/subscriptions.db"
BOTS_DIR = "/root/telegram-bot-builder/app/bots_storage"

# Заглушки вместо реальных ссылок ЮKassa
LINKS = {
    "1_month": "https://example.com/pay/1month",
    "3_months": "https://example.com/pay/3months",
    "12_months": "https://example.com/pay/12months"
}

async def get_token_for_bot(bot_id: str) -> str:
    env_path = Path(f"{BOTS_DIR}/{bot_id}/.env")
    config = dotenv_values(env_path)
    return config.get("BOT_TOKEN", "")

async def get_admin_id_for_bot(bot_id: str) -> int:
    env_path = Path(f"{BOTS_DIR}/{bot_id}/.env")
    config = dotenv_values(env_path)
    return int(config.get("ADMIN_IDS", "0"))

async def check_subscriptions():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                bot_id TEXT PRIMARY KEY,
                created_at TEXT,
                active INTEGER,
                paid INTEGER
            )
        """)
        cursor = await db.execute("SELECT bot_id, created_at, paid, active FROM subscriptions")
        bots = await cursor.fetchall()

        for bot_id, created_at, paid, active in bots:
            if not paid and active:
                created_time = datetime.fromisoformat(created_at)
                if datetime.now() - created_time >= timedelta(days=3):
                    print(f"⛔ Отключаю бот {bot_id} — срок подписки истёк")

                    # Останавливаем и удаляем контейнер
                    subprocess.run(["docker", "stop", f"bot_{bot_id}"])
                    subprocess.run(["docker", "rm", f"bot_{bot_id}"])

                    # Обновляем БД
                    await db.execute("UPDATE subscriptions SET active = 0 WHERE bot_id = ?", (bot_id,))
                    await db.commit()

                    # Уведомляем администратора
                    try:
                        bot_token = await get_token_for_bot(bot_id)
                        admin_id = await get_admin_id_for_bot(bot_id)

                        if bot_token and admin_id:
                            bot = Bot(token=bot_token)

                            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                                [types.InlineKeyboardButton(text="Продлить на 1 месяц", url=LINKS["1_month"])],
                                [types.InlineKeyboardButton(text="На 3 месяца", url=LINKS["3_months"])],
                                [types.InlineKeyboardButton(text="На 12 месяцев", url=LINKS["12_months"])]
                            ])

                            await bot.send_message(
                                chat_id=admin_id,
                                text=(
                                    "⛔ *Подписка бота истекла.*\n\n"
                                    "Ваш бот был *остановлен*, потому что вы не оплатили подписку.\n\n"
                                    "Вы можете продлить его, выбрав один из вариантов ниже:"
                                ),
                                reply_markup=keyboard,
                                parse_mode="Markdown"
                            )
                    except Exception as e:
                        print(f"Не удалось уведомить администратора бота {bot_id}: {e}")

if __name__ == "__main__":
    asyncio.run(check_subscriptions())
