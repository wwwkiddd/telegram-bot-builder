import os
import shutil
from uuid import uuid4
from pathlib import Path
from dotenv import set_key

from app.backend.models import BotRequest


BOTS_DIR = os.getenv("BOTS_DIR", "app/bots_storage")
TEMPLATE_PATH = os.getenv("TEMPLATE_BOT_DIR", "app/template_bot")

async def create_bot_instance(bot_data: BotRequest) -> str:
    bot_id = str(uuid4())[:8]
    bot_path = Path(f"{BOTS_DIR}/{bot_id}")

    # Создаем папку для бота
    shutil.copytree(TEMPLATE_PATH, bot_path)

    # Копируем .env.template как .env
    env_path = bot_path / ".env"
    shutil.copy(bot_path / ".env.template", env_path)

    # Подставляем данные
    set_key(str(env_path), "BOT_TOKEN", bot_data.bot_token)
    set_key(str(env_path), "ADMIN_IDS", str(bot_data.admin_id))

    # Собираем Docker-образ
    os.system(f"docker build -t bot_{bot_id} {bot_path}")

    # Запускаем контейнер
    os.system(f"docker run -d --env-file {env_path} --name bot_{bot_id} bot_{bot_id}")

    return bot_id
