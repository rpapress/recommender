import asyncio
import aiohttp
import os
from bot.db.connect import db
import json
import time
from bot.db.models import (
    Message,
    OutgoingMessageStatus
)
from bot.settings.logger import log_info, log_error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import requests


response_timers = {}

class WhatsAppBot:
    def __init__(self, app, id_instance, api_token_instance, db):
        self.app = app
        self.id_instance = id_instance
        self.api_token_instance = api_token_instance
        self.db = db
        self.base_url = f"https://api.green-api.com/waInstance{self.id_instance}"
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=5)

    async def schedule_reboot(self):
        """Планировщик перезапуска аккаунта каждые 8 часов"""
        while self.running:
            try:
                await self.reboot_account()
                # Ждем 8 часов
                await asyncio.sleep(8 * 60 * 60)  # 8 часов в секундах
            except Exception as e:
                log_error(f"Ошибка в планировщике перезапуска: {str(e)}")
                # В случае ошибки жду 5 минут и пробую снова
                await asyncio.sleep(300)
                
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
        
    async def receive_notification(self):
        """Получение уведомления от GreenAPI"""
        url = f"{self.base_url}/receiveNotification/{self.api_token_instance}"
        max_retries = 3
        retry_delay = 5  # секунд между попытками
        timeout = aiohttp.ClientTimeout(total=30)  # увеличенный таймаут

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data:  # Если есть уведомление
                                receipt_id = data.get('receiptId')
                                body = data.get('body')  # Получаем тело уведомления
                                if body:  # Проверяем, что тело существует
                                    with self.app.app_context():
                                        await self.process_webhook(body, receipt_id)
                                        await self.delete_notification(receipt_id)
                                return True
                        return False

            except asyncio.TimeoutError:
                log_error(f"Таймаут при попытке {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:  # Если это не последняя попытка
                    await asyncio.sleep(retry_delay)
                continue
                
            except aiohttp.ClientError as e:
                log_error(f"Ошибка подключения при попытке {attempt + 1}/{max_retries}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue
                
            except Exception as e:
                log_error(f"Неожиданная ошибка при получении уведомления (попытка {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                continue

        log_error("Все попытки получения уведомления исчерпаны")
        return False
    
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

    async def save_outgoing_message(self, data):
        """Сохранение исходящего сообщения"""
        # Получение timestamp из запроса
        timestamp = data.get('timestamp', int(time.time()))
        # Преобразование Unix-времени в datetime
        timestamp = datetime.fromtimestamp(timestamp)

        try:
            message_data = data.get('messageData', {})
            chat_id = data.get('chatId')
            
            # Получаем информацию о контакте
            contact_info = await self.get_contact_info(chat_id)
            
            # Используем name или contactName, смотря что доступно
            sender_name = contact_info.get('name', '') if contact_info else ''
            log_info(f'SENDER={sender_name}')

            message = Message(
                receipt_id=data.get('receiptId'),
                webhook_type='outgoing',
                id_message=data.get('idMessage'),
                is_from_client=False,
                instance_id=data.get('instanceData', {}).get('idInstance'),
                instance_wid=data.get('instanceData', {}).get('wid'),
                sender_chat_id=chat_id,
                sender_name=sender_name,
                message_type=message_data.get('typeMessage'),
                message_text=message_data.get('textMessageData', {}).get('textMessage', ''),
                timestamp=timestamp
            )
            
            self.db.session.add(message)
            self.db.session.commit()
            log_info(f"Сохранено исходящее сообщение: {message.id}, sender_name: {sender_name}")
            
        except Exception as e:
            log_error(f"Ошибка сохранения исходящего сообщения: {str(e)}")
            self.db.session.rollback()
            
    async def process_webhook(self, data, receipt_id):
        """Обработка входящего вебхука"""
        try:
            webhook_type = data.get('typeWebhook')
            if not webhook_type:
                return
            
            log_info(f"Получен webhook типа: {webhook_type}, данные: {data}")

            if webhook_type == 'incomingMessageReceived':
                # Проверяем, является ли отправитель менеджером
                sender_id = data.get('senderData', {}).get('sender')
                if sender_id == data.get('instanceData', {}).get('wid'):
                    # Если сообщение от менеджера, отменяем таймер для этого чата
                    chat_id = data.get('senderData', {}).get('chatId')
                    await self.cancel_response_timer({'chatId': chat_id})
                    log_info(f"Таймер отменен из-за ответа менеджера для чата {chat_id}")
                else:
                    # Если сообщение от клиента
                    await self.save_incoming_message(data, receipt_id)
                    await self.start_response_timer(data)

            elif webhook_type == 'outgoingMessageStatus':
                # Отменяем таймер при отправке сообщения менеджером
                chat_id = data.get('chatId')
                await self.cancel_response_timer({'chatId': chat_id})
                
                await self.save_outgoing_message_from_status(data, receipt_id)
                await self.update_message_status(data)
            elif webhook_type == 'outgoingAPIMessageReceived':
                await self.save_outgoing_message(data)
                
        except Exception as e:
            log_error(f"Ошибка обработки вебхука: {str(e)}")
    
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
        
    async def start_response_timer(self, data):
        """Запуск таймера ожидания ответа менеджера"""
        sender_chat_id = data.get('senderData', {}).get('chatId')
        
        # Проверка на None
        if not sender_chat_id:
            log_error(f"Не удалось получить sender_chat_id из данных: {data}")
            return
        
        # Если уже есть активный таймер для этого клиента, отменяем его
        if sender_chat_id in response_timers:
            response_timers[sender_chat_id].cancel()
        
        # Запускаем новый таймер
        timer = asyncio.create_task(self.send_scripted_message(sender_chat_id, delay=20))
        response_timers[sender_chat_id] = timer
        log_info(f"Запущен таймер ответа для клиента {sender_chat_id}")

    async def cancel_response_timer(self, data):
        """Отмена таймера, если менеджер ответил"""
        try:
            sender_chat_id = data.get('chatId')
            if sender_chat_id in response_timers:
                response_timers[sender_chat_id].cancel()
                del response_timers[sender_chat_id]
                log_info(f"Таймер отменен для чата {sender_chat_id}")
        except Exception as e:
            log_error(f"Ошибка при отмене таймера: {str(e)}")

    async def send_scripted_message(self, sender_chat_id, delay):
        """Отправка заскриптованного сообщения после тайм-аута"""
        try:
            if not sender_chat_id:
                log_error("sender_chat_id is None, отправка сообщения невозможна")
                return
            
            # Проверяем, есть ли активные сообщения от менеджера за последние N минут
            recent_messages = await self.get_recent_manager_messages(sender_chat_id)
            if recent_messages:
                log_info(f"Найдены недавние сообщения менеджера для {sender_chat_id}, отмена автоответа")
                return
                
            await asyncio.sleep(delay)
            
            # Повторная проверка перед отправкой
            if sender_chat_id not in response_timers:
                log_info(f"Таймер был отменен для {sender_chat_id}, отмена отправки сообщения")
                return
                
            log_info(f"Отправка заскриптованного сообщения клиенту {sender_chat_id}, так как ответа менеджера не поступило")
            
            chat_id = f"{sender_chat_id}"
            if not '@' in chat_id:
                chat_id = f"{sender_chat_id}@c.us"
                
            message = "Извините за задержку, менеджер скоро ответит."
            await self.send_message(chat_id, message)
            
        except Exception as e:
            log_error(f"Ошибка при отправке заскриптованного сообщения: {str(e)}")
        
    async def get_recent_manager_messages(self, chat_id, minutes=5):
        """Проверка наличия недавних сообщений от менеджера"""
        try:
            current_time = datetime.now()
            time_threshold = current_time - timedelta(minutes=minutes)
            
            # Получаем сообщения от менеджера за последние N минут
            # Добавляем условие send_by_api == False чтобы исключить автоматические сообщения
            recent_messages = Message.query.filter(
                Message.sender_chat_id == chat_id,
                Message.is_from_client == False,
                Message.send_by_api == False,
                Message.timestamp >= time_threshold
            ).all()
            
            return len(recent_messages) > 0
        except Exception as e:
            log_error(f"Ошибка при проверке недавних сообщений: {str(e)}")
            return False
    
    async def save_incoming_message(self, data, receipt_id):
        """Сохранение входящего сообщения"""
        try:
            message_data = data.get('messageData', {})
            sender_data = data.get('senderData', {})
            
            timestamp = data.get('timestamp', int(time.time()))
            # Преобразование Unix-времени в datetime
            timestamp = datetime.fromtimestamp(timestamp)


            # Проверяем оба возможных места хранения текста
            message_text = (
                message_data.get('textMessageData', {}).get('textMessage', '') or 
                message_data.get('extendedTextMessageData', {}).get('text', '')
            )

            message = Message(
                receipt_id=receipt_id,
                webhook_type='incoming',
                id_message=data.get('idMessage'),
                is_from_client=True,
                instance_id=self.id_instance,
                instance_wid=data.get('instanceData', {}).get('wid', ''),
                sender_chat_id=sender_data.get('chatId'),
                sender_name=sender_data.get('senderName'),
                sender_contact_name=sender_data.get('senderContact', {}).get('name'),
                message_type=message_data.get('typeMessage'),
                message_text=message_text,
                message_url=message_data.get('extendedTextMessageData', {}).get('jpegThumbnail'),
                timestamp=timestamp
            )
            
            self.db.session.add(message)
            self.db.session.commit()
            log_info(f"Сохранено входящее сообщение: {message.id}")
            
            
        except Exception as e:
            log_error(f"Ошибка сохранения входящего сообщения: {str(e)}")
            self.db.session.rollback()

    async def save_outgoing_message_from_status(self, data, receipt_id):
        """Сохранение исходящего сообщения из уведомления о статусе"""
        try:
            send_by_api = data.get('sendByApi', False)
            manager_phone_from_data = data.get('instanceData', {}).get('wid')
            client_phone_from_data = data.get('chatId', '')
            # Получаю информацию о контакте
            manager_info = await self.get_contact_info(manager_phone_from_data)
            client_info = await self.get_contact_info(client_phone_from_data)
            
            # Получаю имя
            manager_name = manager_info.get('name', '') if manager_info else ''
            client_name = client_info.get('name', '') if client_info else ''
            log_info(f'MANAGER={manager_name}')
            log_info(f'CLIENT={client_name}')
    
            # Получение timestamp из запроса
            timestamp = data.get('timestamp', int(time.time()))
            # Преобразование Unix-времени в datetime
            timestamp = datetime.fromtimestamp(timestamp)
            # Проверя, существует ли уже сообщение с таким id_message
            existing_message = Message.query.filter_by(id_message=data.get('idMessage')).first()
            if existing_message:
                return  # Если сообщение уже существует, не создаем новое

            # Получаю текст сообщения асинхронно
            message_text = await self.get_message_text(
                data.get('chatId'),
                data.get('idMessage')
            )
            
            message = Message(
                receipt_id=receipt_id,
                webhook_type='outgoing',
                id_message=data.get('idMessage'),
                is_from_client=False,
                instance_id=data.get('instanceData', {}).get('idInstance'),
                instance_wid=data.get('instanceData', {}).get('wid'),
                sender_chat_id=data.get('chatId'),
                message_type='textMessage',
                sender_name=client_name,
                sender_contact_name=manager_name,
                message_text=message_text,
                timestamp=timestamp,
                send_by_api=send_by_api
            )
            
            self.db.session.add(message)
            self.db.session.commit()
            log_info(f"Сохранено исходящее сообщение из статуса: {message.id}")
            
        except Exception as e:
            log_error(f"Ошибка сохранения исходящего сообщения из статуса: {str(e)}")
            self.db.session.rollback()

    async def update_message_status(self, data):
        """Обновление статуса сообщения"""
        try:
            status = OutgoingMessageStatus(
                message_id=data.get('idMessage'),
                chat_id=data.get('chatId'),
                status=data.get('status'),
                send_by_api=data.get('sendByApi', False)
            )
            
            self.db.session.add(status)
            self.db.session.commit()
            log_info(f"Обновлен статус сообщения: {status.id}")
            
        except Exception as e:
            log_error(f"Ошибка обновления статуса сообщения: {str(e)}")
            self.db.session.rollback()

    async def run(self):
        """Запуск бота"""
        try:
            # Первоначальный перезапуск при старте
            await self.reboot_account()

            # Запускаем планировщик перезапуска в отдельной задаче
            reboot_scheduler = asyncio.create_task(self.schedule_reboot())

            while self.running:
                try:
                    if await self.receive_notification():
                        continue
                    await asyncio.sleep(1)
                except Exception as e:
                    log_error(f"Ошибка в цикле работы бота: {str(e)}")
                    await asyncio.sleep(5)

            # Отменяем планировщик при остановке бота
            reboot_scheduler.cancel()
            
        except Exception as e:
            log_error(f"Критическая ошибка в работе бота: {str(e)}")
        finally:
            # Убеждаемся, что планировщик остановлен
            if 'reboot_scheduler' in locals() and not reboot_scheduler.done():
                reboot_scheduler.cancel()

    def stop(self):
        """Остановка бота"""
        self.running = False
        log_info("Запрошена остановка бота")

    def __del__(self):
        """Закрываем пул потоков при удалении объекта"""
        self.executor.shutdown(wait=False)