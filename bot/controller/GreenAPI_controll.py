import aiohttp
import logging
from bot.config import GREEN_API_TOKEN, GREEN_API_ID, GREEN_API_URL


class GreenAPI:
    def __init__(self, app):
        self.app = app
        self.url = GREEN_API_URL
        self.id = GREEN_API_ID
        self.token = GREEN_API_TOKEN
        self.api_get_message = f"{self.url}/waInstance{self.id}/receiveNotification/{self.token}"

    async def get_messages(self):
        """Получение сообщений через API"""
        async with aiohttp.ClientSession() as session:
            async with session.get(self.api_get_message) as response:
                if response.status == 200:
                    messages = await response.json()
                    if messages:
                        print('[Входящее сообщение]', messages)
                    else:
                        print("Нет новых сообщений. Ожидание...")

                    return messages
                else:
                    print(f"Ошибка API: {response.status}")
                    return []

    async def delete_notification(self, receipt_id):
        """Удаление уведомления по receipt_id с помощью Green API"""
        try:
            delete_url = f"{self.url}/waInstance{self.id}/deleteNotification/{self.token}/{receipt_id}"
            print(f"[delete_notification] Удаление уведомления по URL: {delete_url}")

            async with aiohttp.ClientSession() as session:
                async with session.delete(delete_url) as response:
                    if response.status == 200:
                        print(f"Уведомление с receipt_id {receipt_id} успешно удалено.")
                    else:
                        print(f"Ошибка при удалении уведомления: {response.status} - {await response.text()}")
        except Exception as e:
            print(f"Ошибка при удалении уведомления: {e}")

    async def send_message(self, phone_number, message):
        """Функция отправки сообщения через Green API"""
        send_url = f"{self.url}/waInstance{self.id}/sendMessage/{self.token}"
        data = {
            "chatId": f"{phone_number}@c.us",
            "message": message
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(send_url, json=data) as response:
                if response.status == 200:
                    print(f"Сообщение '{message}' отправлено на номер {phone_number}")
                    logging.info(f"Сообщение '{message}' отправлено на номер {phone_number}")
                else:
                    print(f"Ошибка при отправке сообщения: {response.status}")
                    logging.info(f"Ошибка при отправке сообщения: {response.status}")