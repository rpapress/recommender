from datetime import datetime
from bot.db.models import Notification, ChatHistory
from bot.db.connect import db


class WhatsAppBotUtils:
    @staticmethod
    async def save_notification(
        receipt_id, 
        phone_number, 
        message_type, 
        send_by_api, 
        message_text, 
        received_at, 
        message_id,
        ):
        if isinstance(received_at, int):
            received_at = datetime.fromtimestamp(received_at)
        notification = Notification(
            receipt_id=receipt_id,
            phone_number=phone_number,
            message_text=message_text,
            message_type=message_type,
            message_id=message_id,
            received_at=received_at,
            send_by_api=send_by_api
        )
        db.session.add(notification)
        db.session.commit()

    @staticmethod
    async def clear_context(green_api, client):
        try:
            await green_api.send_message(client.phone_number, "Контекст успешно удалён. Если у вас есть другие вопросы или пожелания, дайте знать!")

            chat_history = ChatHistory.query.filter_by(phone_number=client.phone_number).all()

            for entry in chat_history:
                db.session.delete(entry)

            client.status = 'не отвечен'
            db.session.commit()

            print(f"Контекст для номера {client.phone_number} успешно удален.")
        except Exception as e:
            print(f"Ошибка при удалении контекста: {e}")
            db.session.rollback()
