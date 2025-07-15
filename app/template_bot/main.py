import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, List

import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS').split(',')))
DB_PATH = os.getenv('DB_PATH', 'bot_database.db')
REVIEWS_CHAT_LINK = os.getenv('REVIEWS_CHAT_LINK', 'https://t.me/your_reviews_chat')

payment_context = {}  # user_id -> {slot, service, prepayment}

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class Form(StatesGroup):
    language = State()
    name = State()
    phone = State()
    gender = State()
    birth_date = State()
    service = State()
    slot = State()
    anamnesis = State()


class AdminForm(StatesGroup):
    add_slots = State()


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.path)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                language TEXT NOT NULL,
                name TEXT,
                phone TEXT,
                gender TEXT,
                birth_date TEXT,
                registered INTEGER DEFAULT 0
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datetime TEXT NOT NULL,
                available INTEGER DEFAULT 1
            )
        """)
        await self.conn.commit()

    async def add_user(self, user_id: int, language: str):
        await self.conn.execute(
            "INSERT OR IGNORE INTO users (id, language) VALUES (?, ?)",
            (user_id, language)
        )
        await self.conn.commit()

    async def update_user(self, user_id: int, **kwargs):
        keys = list(kwargs.keys())
        values = list(kwargs.values())
        set_clause = ", ".join([f"{k} = ?" for k in keys])
        await self.conn.execute(
            f"UPDATE users SET {set_clause} WHERE id = ?",
            values + [user_id]
        )
        await self.conn.commit()

    async def get_user(self, user_id: int) -> Optional[dict]:
        cursor = await self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            keys = [column[0] for column in cursor.description]
            return dict(zip(keys, row))
        return None

    async def add_slots(self, slots: List[str]):
        current_year = datetime.now().year
        formatted_slots = []

        for slot in slots:
            slot = slot.strip()
            if not slot:
                continue

            try:
                dt = datetime.strptime(slot, "%d.%m %H:%M")
                dt = dt.replace(year=current_year)
                formatted_slots.append(dt.strftime("%d.%m.%Y %H:%M"))
            except ValueError:
                continue

        if formatted_slots:
            for slot in formatted_slots:
                await self.conn.execute(
                    "INSERT INTO slots (datetime, available) VALUES (?, ?)",
                    (slot, 1)
                )
            await self.conn.commit()
            return len(formatted_slots)
        return 0

    async def get_available_slots(self) -> List[dict]:
        cursor = await self.conn.execute(
            "SELECT id, datetime FROM slots WHERE available = 1 ORDER BY datetime"
        )
        rows = await cursor.fetchall()
        return [{"id": row[0], "datetime": row[1]} for row in rows]

    async def close(self):
        await self.conn.close()


db = Database(DB_PATH)


async def language_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Русский", callback_data="lang_ru")
    builder.button(text="English", callback_data="lang_en")
    return builder.as_markup()


async def show_main_menu(user_id: int, language: str):
    builder = ReplyKeyboardBuilder()
    buttons = [
        "Записаться на прием", "Отзывы", "FAQ", "Магазин", "Порекомендовать"
    ] if language == "ru" else [
        "Make an appointment", "Reviews", "FAQ", "Shop", "Recommend"
    ]
    for btn in buttons:
        builder.button(text=btn)
    markup = builder.as_markup(resize_keyboard=True)
    await bot.send_message(user_id, "Выберите действие:" if language == "ru" else "Choose an option:",
                           reply_markup=markup)


async def show_admin_menu(user_id: int):
    builder = ReplyKeyboardBuilder()
    builder.button(text="Добавить свободные окна")
    builder.button(text="Список записей")
    markup = builder.as_markup(resize_keyboard=True)
    await bot.send_message(user_id, "Админ-панель:", reply_markup=markup)


@dp.message(F.text.startswith("/start"))
async def cmd_start(message: types.Message, state: FSMContext):
    try:
        user_id = message.from_user.id
        user = await db.get_user(user_id)

        if user_id in ADMIN_IDS:
            if not user:
                await db.add_user(user_id, language="ru")
            await show_admin_menu(user_id)
            return

        if user and user.get("registered"):
            await show_main_menu(user_id, user['language'])
        else:
            await db.add_user(user_id, language="ru")
            await state.set_state(Form.language)
            await message.answer("Выберите язык / Choose language:", reply_markup=await language_keyboard())

    except Exception as e:
        logger.error(f"Error in cmd_start: {e}")
        await message.answer("Произошла ошибка. Пожалуйста, попробуйте позже.")


@dp.callback_query(F.data.startswith("lang_"))
async def process_language(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await db.update_user(callback.from_user.id, language=lang)
    await state.set_state(Form.name)
    await callback.message.answer("Введите ваше имя:" if lang == "ru" else "Enter your name:")


@dp.message(Form.name)
async def process_name(message: types.Message, state: FSMContext):
    await db.update_user(message.from_user.id, name=message.text)
    user = await db.get_user(message.from_user.id)
    await state.set_state(Form.phone)
    await message.answer("Введите ваш номер телефона:" if user['language'] == "ru" else "Enter your phone number:")


@dp.message(Form.phone)
async def process_phone(message: types.Message, state: FSMContext):
    await db.update_user(message.from_user.id, phone=message.text)
    user = await db.get_user(message.from_user.id)
    await state.set_state(Form.gender)
    await message.answer("Ваш пол (м/ж):" if user['language'] == "ru" else "Your gender (m/f):")


@dp.message(Form.gender)
async def process_gender(message: types.Message, state: FSMContext):
    await db.update_user(message.from_user.id, gender=message.text)
    user = await db.get_user(message.from_user.id)
    await state.set_state(Form.birth_date)
    await message.answer("Дата рождения (ДД.ММ.ГГГГ):" if user['language'] == "ru" else "Birth date (DD.MM.YYYY):")


@dp.message(Form.birth_date)
async def process_birth_date(message: types.Message, state: FSMContext):
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        await db.update_user(
            message.from_user.id,
            birth_date=message.text,
            registered=1
        )
        user = await db.get_user(message.from_user.id)
        await message.answer("Регистрация завершена!" if user['language'] == "ru" else "Registration complete!")
        await state.clear()
        await show_main_menu(message.from_user.id, user['language'])
    except ValueError:
        user = await db.get_user(message.from_user.id)
        await message.answer("Неверный формат даты. Попробуйте снова." if user[
                                                                              'language'] == "ru" else "Invalid date format. Try again.")


@dp.message(F.text.in_(["Магазин", "Shop"]))
async def shop_coming_soon(message: types.Message):
    await message.answer("Скоро тут будет магазин!" if message.text == "Магазин" else "Shop coming soon!")


@dp.message(F.text.in_(["Порекомендовать", "Recommend"]))
async def referral_coming_soon(message: types.Message):
    await message.answer(
        "Скоро тут будет реферальная система!" if message.text == "Порекомендовать" else "Referral system coming soon!")


@dp.message(F.text.in_(["FAQ"]))
async def faq_message(message: types.Message):
    await message.answer("Популярные вопросы и ответы:\n\nВопрос 1 — Ответ 1\nВопрос 2 — Ответ 2")


@dp.message(F.text.in_(["Отзывы", "Reviews"]))
async def reviews_message(message: types.Message):
    await message.answer(
        f"Наши отзывы: {REVIEWS_CHAT_LINK}" if message.text == "Отзывы" else f"Our reviews: {REVIEWS_CHAT_LINK}")


@dp.message(F.text.in_(["Записаться на прием", "Make an appointment"]))
async def start_appointment(message: types.Message, state: FSMContext):
    user = await db.get_user(message.from_user.id)
    await state.set_state(Form.service)

    services = ["Чистка лица", "Пилинг", "Массаж лица", "Маска"]
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.button(text=s, callback_data=f"service_{s}")
    builder.adjust(1)

    await message.answer("Выберите услугу:" if user['language'] == 'ru' else "Choose a service:",
                         reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("service_"))
async def choose_service(callback: types.CallbackQuery, state: FSMContext):
    service = callback.data.split("_", 1)[1]
    await state.update_data(service=service)

    user = await db.get_user(callback.from_user.id)
    lang = user['language'] if user else 'ru'

    slots = await db.get_available_slots()
    if not slots:
        await callback.message.answer("Нет доступных окон." if lang == 'ru' else "No available slots.")
        await state.clear()
        return

    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.button(text=slot["datetime"], callback_data=f"slot_{slot['id']}")
    builder.adjust(1)

    await state.set_state(Form.slot)
    await callback.message.answer("Выберите время:" if lang == 'ru' else "Choose time:",
                                  reply_markup=builder.as_markup())


@dp.callback_query(F.data.startswith("slot_"), Form.slot)
async def choose_slot(callback: types.CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split("_", 1)[1])
    await state.update_data(slot_id=slot_id)
    await state.set_state(Form.anamnesis)

    user = await db.get_user(callback.from_user.id)
    lang = user['language'] if user else 'ru'

    await callback.message.answer(
        "Введите ваш анамнез (аллергии, кожные проблемы и т.д.):"
        if lang == 'ru' else
        "Enter your medical history (allergies, skin problems, etc.):"
    )


@dp.message(Form.anamnesis)
async def submit_anamnesis(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    slot_id = data["slot_id"]
    await db.conn.execute("UPDATE slots SET available = 0 WHERE id = ?", (slot_id,))
    await db.conn.commit()
    service = data["service"]
    anamnesis = message.text

    await state.clear()

    for admin_id in ADMIN_IDS:
        await bot.send_message(
            admin_id,
            f"📋 Новая заявка:\n\nПользователь: {user['name']}\nУслуга: {service}\nАнамнез: {anamnesis}\nСлот ID: {slot_id}",
            reply_markup=InlineKeyboardBuilder()
            .button(text="✅ Подтвердить", callback_data=f"confirm_{message.from_user.id}_{slot_id}_{service}")
            .button(text="❌ Отменить", callback_data=f"cancel_{message.from_user.id}")
            .as_markup()
        )

    await message.answer("Ваша заявка отправлена администратору. Ожидайте подтверждения.")


@dp.callback_query(F.data.startswith("cancel_"))
async def admin_cancel(callback: types.CallbackQuery):
    try:
        _, user_id = callback.data.split("_")
        user_id = int(user_id)

        await callback.message.edit_reply_markup()
        await bot.send_message(user_id, "❌ Ваша запись была отменена администратором.")
        await callback.message.answer("Запись отменена.")
    except Exception as e:
        await callback.message.answer("Ошибка при отмене.")
        logging.exception(e)


@dp.callback_query(F.data.startswith("confirm_"))
async def admin_confirm(callback: types.CallbackQuery):
    try:
        _, user_id, slot_id, service = callback.data.split("_", 3)
        user_id, slot_id = int(user_id), int(slot_id)

        cursor = await db.conn.execute("SELECT datetime FROM slots WHERE id = ?", (slot_id,))
        row = await cursor.fetchone()
        if not row:
            await callback.message.answer("Слот не найден.")
            return
        slot_time = row[0]

        payment_context[user_id] = {
            "slot": slot_time,
            "service": service
        }

        await callback.message.answer(
            "Введите сумму предоплаты и реквизиты (например, 900₽ на карту 1234 5678 9012 3456):")
    except Exception as e:
        await callback.message.answer("Ошибка при подтверждении.")
        logging.exception(e)


@dp.message()
async def receive_payment_info(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        for user_id, ctx in payment_context.items():
            slot_time = ctx["slot"]
            service = ctx["service"]
            text = f"""
✅ Ваша запись подтверждена!

🧴 Услуга: {service}
🕒 Дата и время: {slot_time}

💰 Предоплата: {message.text}

Пожалуйста, подтвердите оплату:
"""
            await bot.send_message(
                user_id,
                text,
                reply_markup=InlineKeyboardBuilder()
                .button(text="✅ Оплатил", callback_data=f"paid_{user_id}")
                .button(text="❌ Отменить", callback_data=f"decline_{user_id}")
                .as_markup()
            )
        payment_context.clear()


@dp.callback_query(F.data.startswith(("paid_", "decline_")))
async def payment_response(callback: types.CallbackQuery):
    action, user_id = callback.data.split("_", 1)
    user_id = int(user_id)

    user = await db.get_user(user_id)
    if action == "paid":
        await callback.message.answer("✅ Оплата получена! До встречи!")
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"👤 Пользователь {user['name']} оплатил запись.")
    else:
        await callback.message.answer("❌ Запись отменена.")
        for admin_id in ADMIN_IDS:
            await bot.send_message(admin_id, f"⚠️ Пользователь {user['name']} отменил запись.")


@dp.message(F.text == "Добавить свободные окна")
async def handle_add_slots(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
        await state.set_state(AdminForm.add_slots)
        await message.answer(
            "Введите даты и время через Enter (например:\n16.03 17:00\n17.03 14:30):"
        )


@dp.message(AdminForm.add_slots)
async def add_slots_process(message: types.Message, state: FSMContext):
    raw_slots = message.text.strip().splitlines()
    added = await db.add_slots(raw_slots)

    if added > 0:
        await message.answer(f"✅ Добавлено {added} свободных окон.")
    else:
        await message.answer("⚠️ Не удалось добавить ни одного окна. Проверьте формат даты (дд.мм чч:мм).")

    await state.clear()




@dp.message(F.text == "Список записей")
async def handle_list_appointments(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
        cursor = await db.conn.execute("SELECT datetime FROM slots WHERE available = 0 ORDER BY datetime")
        rows = await cursor.fetchall()
        if not rows:
            await message.answer("Нет занятых слотов.")
        else:
            text = "Занятые слоты:\n" + "\n".join([row[0] for row in rows])
            await message.answer(text)


async def on_startup():
    await db.connect()
    logger.info("Бот запущен и подключен к базе данных")
    default_slots = ["21.05 12:00", "21.05 15:00", "22.05 18:30"]
    existing = await db.get_available_slots()
    if not existing:
        await db.add_slots(default_slots)
        logger.info("Добавлены тестовые окна по умолчанию")


async def on_shutdown():
    await db.close()
    logger.info("Бот остановлен, соединение с базой данных закрыто")


async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())