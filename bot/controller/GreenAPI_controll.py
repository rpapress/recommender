import aiohttp
import logging
from bot.settings.config import GREEN_API_TOKEN, GREEN_API_ID, GREEN_API_URL
from bot.settings.logger import log_info, log_error


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
                        log_info(f'[Входящее сообщение] {messages}')
                        print('[Входящее сообщение]', messages)
                    else:
                        print("Нет новых сообщений. Ожидание...")

                    return messages
                else:
                    print(f"Ошибка API: {response.status}")
                    return []

    async def get_message(self, chat_id, message_id):
        """Получение конкретного сообщения по chatId и idMessage"""
        get_message_url = f"{self.url}/waInstance{self.id}/getMessage/{self.token}"
        data = {
            "chatId": chat_id,
            "idMessage": message_id
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(get_message_url, json=data) as response:
                if response.status == 200:
                    message_data = await response.json()
                    print(f"Получено сообщение: {message_data}")
                    logging.info(f"Получено сообщение: {message_data}")
                    return message_data
                else:
                    print(f"Ошибка при получении сообщения: {response.status}")
                    logging.error(f"Ошибка при получении сообщения: {response.status} - {await response.text()}")
                    return None
                
    async def delete_notification(self, receipt_id):
        """Удаление уведомления по receipt_id с помощью Green API"""
        try:
            delete_url = f"{self.url}/waInstance{self.id}/deleteNotification/{self.token}/{receipt_id}"
            log_info(f"[delete_notification] Удаление уведомления по URL: {delete_url}")

            async with aiohttp.ClientSession() as session:
                async with session.delete(delete_url) as response:
                    if response.status == 200:
                        log_info(f"Уведомление с receipt_id {receipt_id} успешно удалено.")
                    else:
                        log_error(f"Ошибка при удалении уведомления: {response.status} - {await response.text()}")
        except Exception as e:
            log_error(f"Ошибка при удалении уведомления: {e}")

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

    async def send_image(self, phone_number, image_url, caption=""):
        """Функция для отправки изображения через Green API"""
        send_file_url = f"{self.url}/waInstance{self.id}/sendFileByUrl/{self.token}"
        data = {
            "chatId": f"{phone_number}@c.us",
            "urlFile": image_url,
            "fileName": "image.jpg",
            "caption": caption
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(send_file_url, json=data) as response:
                if response.status == 200:
                    print(f"Изображение отправлено на номер {phone_number}")
                    logging.info(f"Изображение отправлено на номер {phone_number}")
                else:
                    print(f"Ошибка при отправке изображения: {response.status}")
                    logging.error(f"Ошибка при отправке изображения: {response.status} - {await response.text()}")