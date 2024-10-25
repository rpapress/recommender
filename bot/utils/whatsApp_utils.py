# from bot.models import Notification, ChatHistory
from bot.db import db


class WhatsAppBotUtils:
    @staticmethod
    async def save_notification(receipt_id, phone_number, message_text):
        notification = Notification(
            receipt_id=receipt_id,
            phone_number=phone_number,
            message_text=message_text,
            message_type='text'
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

    @staticmethod
    async def send_to_manager(green_api, response_text):
        manager_phone_numbers = ["77759419359", "77072508661"]
        for number in manager_phone_numbers:
            try:
                await green_api.send_message(number, response_text)
            except Exception as e:
                print(f"Ошибка при отправке сообщения менеджеру {number}: {e}")