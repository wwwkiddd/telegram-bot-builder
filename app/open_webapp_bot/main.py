from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import os
from dotenv import load_dotenv
from app.shared.yookassa_api import create_payment_link
from app.shared.subscription_db import set_subscription


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

@dp.message(F.text.lower() == "/start")
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Создать бота", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="💰 Оплатить подписку", callback_data="pay")],
        [InlineKeyboardButton(text="🛒 Магазин", callback_data="shop")],
        [InlineKeyboardButton(text="🛠 Техподдержка", url="https://t.me/nikita_support")]
    ])
    await message.answer("Добро пожаловать! Выберите действие:", reply_markup=keyboard)

@dp.callback_query(F.data == "pay")
async def show_payment_options(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 месяц — 300 ₽", callback_data="pay_1")],
        [InlineKeyboardButton(text="3 месяца — 800 ₽", callback_data="pay_3")],
        [InlineKeyboardButton(text="12 месяцев — 3000 ₽", callback_data="pay_12")]
    ])
    await callback.message.answer("Выберите срок подписки:", reply_markup=keyboard)

@dp.callback_query(F.data.in_({"pay_1", "pay_3", "pay_12"}))
async def handle_payment(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    bot_id = f"user_{user_id}"  # или получай из БД

    months = {
        "pay_1": 1,
        "pay_3": 3,
        "pay_12": 12
    }[callback.data]

    price = {
        1: 300,
        3: 800,
        12: 3000
    }[months]

    url = create_payment_link(price, user_id, bot_id)
    await callback.message.answer(f"💳 Перейдите для оплаты:\n{url}")

@dp.callback_query(F.data == "shop")
async def show_shop(callback: types.CallbackQuery):
    await callback.message.answer("🛒 Магазин скоро будет доступен!")

async def main():
    print("Бот запускается...")  # Добавьте это для отладки
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("Бот остановлен")  # Сообщение о корректном завершении

if __name__ == "__main__":
    asyncio.run(main())