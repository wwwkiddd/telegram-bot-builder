from yookassa import Configuration, Payment
import uuid

Configuration.account_id = "твой_shop_id"
Configuration.secret_key = "твой_secret_key"


def create_payment_link(amount: int, user_id: int, bot_id: str) -> str:
    payment = Payment.create({
        "amount": {
            "value": f"{amount:.2f}",
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/your_bot"
        },
        "capture": True,
        "description": f"Подписка на бота {bot_id}",
        "metadata": {
            "user_id": str(user_id),
            "bot_id": bot_id
        }
    }, uuid.uuid4())

    return payment.confirmation.confirmation_url
