import os
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from app.backend.models import BotRequest
from app.backend.utils import create_bot_instance
from app.shared.subscription_db import get_expired_bots

load_dotenv()

app = FastAPI()

@app.post("/create_bot/")
async def create_bot(bot_data: BotRequest):
    try:
        bot_id = await create_bot_instance(bot_data)
        return {"status": "ok", "bot_id": bot_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
