from pydantic import BaseModel

class BotRequest(BaseModel):
    bot_token: str
    admin_id: int
