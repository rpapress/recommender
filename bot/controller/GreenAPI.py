import aiohttp
import asyncio
import requests
from datetime import datetime
from bot.settings.logger import log_info, log_error
from bot.settings.config import GREEN_API_TOKEN, GREEN_API_ID, GREEN_API_URL
from concurrent.futures import ThreadPoolExecutor


class GreenAPI:
    def __init__(self, app):
        self.app = app
        self.url = GREEN_API_URL
        self.id_instance = GREEN_API_ID
        self.api_token_instance = GREEN_API_TOKEN
        self.base_url = f"https://api.green-api.com/waInstance{self.id_instance}"
        self.executor = ThreadPoolExecutor(max_workers=5)

    # --------------------------------------------------------------------------------------------------
    # Перезапуск аккаунта
    async def reboot_account(self):
        """Перезапуск аккаунта"""
        try:
            url = f"{self.base_url}/reboot/{self.api_token_instance}"
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: requests.get(url)
            )
            
            if response.status_code == 200:
                reboot_response = response.json()
                if reboot_response.get("isReboot"):
                    log_info(f"Аккаунт успешно перезапущен в {current_time}")
                else:
                    log_error(f"Ошибка при перезапуске аккаунта в {current_time}")
            else:
                log_error(f"Ошибка при запросе перезагрузки: статус {response.status_code} в {current_time}")

        except Exception as e:
            log_error(f"Ошибка при перезапуске аккаунта: {str(e)}")


    # --------------------------------------------------------------------------------------------------
    # Получение текста
    async def get_message_text(self, chat_id, message_id):
        """Получение текста сообщения через API"""
        try:
            url = f"{self.base_url}/getMessage/{self.api_token_instance}"
            payload = {
                "chatId": chat_id,
                "idMessage": message_id
            }
            
            log_info(f"Отправка запроса на получение текста сообщения: chat_id={chat_id}, message_id={message_id}")

            # Выполняем запрос в отдельном потоке
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: requests.post(
                    url,
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                )
            )
            
            if response.status_code == 200:
                message_data = response.json()
                log_info(f'Полученные данные={message_data}')
                return message_data.get('textMessage', '')
            log_error(f"Ошибка при получении текста сообщения: статус {response.status_code}")
            return ''
            
        except Exception as e:
            log_error(f"Ошибка получения текста сообщения: {str(e)}")
            return ''
        
    # --------------------------------------------------------------------------------------------------
    # Получение информации о контакте
    async def get_contact_info(self, chat_id):
        """Получение информации о контакте через API"""
        try:
            url = f"{self.base_url}/getContactInfo/{self.api_token_instance}"
            payload = {
                "chatId": chat_id
            }
            headers = {
                'Content-Type': 'application/json'
            }
            
            log_info(f"Отправка запроса на получение информации о контакте: chat_id={chat_id}")

            # Выполняем запрос в отдельном потоке
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: requests.get(
                    url,
                    json=payload,
                    headers=headers
                )
            )
            
            if response.status_code == 200:
                contact_data = response.json()
                log_info(f'Полученные данные о контакте={contact_data}')
                return contact_data
            
            log_error(f"Ошибка при получении информации о контакте: статус {response.status_code}")
            return None
                
        except Exception as e:
            log_error(f"Ошибка получения информации о контакте: {str(e)}")
            return None
        
    # --------------------------------------------------------------------------------------------------
    # Получить сообщение
    async def get_messages(self):
        """Получение сообщений через API"""
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/waInstance{self.id_instance}/receiveNotification/{self.api_token_instance}"
            async with session.get(url) as response:
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
    
    
    # --------------------------------------------------------------------------------------------------
    # Удалить уведомление
    async def delete_notification(self, receipt_id):
        """Удаление уведомления после обработки"""
        url = f"{self.base_url}/deleteNotification/{self.api_token_instance}/{receipt_id}"
        max_retries = 3
        retry_delay = 5
        timeout = aiohttp.ClientTimeout(total=30)

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.delete(url) as response:
                        if response.status == 200:
                            return True
                        
            except asyncio.TimeoutError:
                log_error(f"Таймаут при удалении уведомления (попытка {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
                
            except aiohttp.ClientError as e:
                log_error(f"Ошибка подключения при удалении уведомления (попытка {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
                
            except Exception as e:
                log_error(f"Неожиданная ошибка при удалении уведомления (попытка {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue

        log_error(f"Не удалось удалить уведомление {receipt_id} после всех попыток")
        return False

    # --------------------------------------------------------------------------------------------------
    # Отправить сообщение
    async def send_message(self, chat_id, message):
        """Функция отправки сообщения через Green API"""
        try:
            url = f"{self.base_url}/sendMessage/{self.api_token_instance}"
            data = {
                "chatId": chat_id,
                "message": message
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            log_info(f"Отправка сообщения на {chat_id}: {message}")
            
            # Выполняем запрос в отдельном потоке
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: requests.post(
                    url,
                    json=data,
                    headers=headers
                )
            )
            
            if response.status_code == 200:
                response_data = response.json()
                log_info(f"Сообщение успешно отправлено: {response_data}")
                return response_data
            else:
                log_error(f"Ошибка при отправке сообщения: статус {response.status_code}")
                return None
                
        except Exception as e:
            log_error(f"Ошибка при отправке сообщения: {str(e)}")
            return None