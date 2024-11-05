import asyncio
import aiohttp
import os
from bot.db.connect import db
# from bot.utils.whatsApp_utils import WhatsAppBotUtils
import json
import time
from bot.db.models import (
    Message,
    OutgoingMessageStatus
)
from bot.stack.traveler import interact_with_chatgpt_async
from bot.stack.prompts import system_prompt, correct_form_prompt
from bot.controller.GreenAPI_controll import GreenAPI
from bot.settings.logger import log_info, log_error
from concurrent.futures import ThreadPoolExecutor
from bot.settings.config import MANAGER_PHONE_NUMBER
from bot.utils.create_link import encode_text_for_url, shorten_url
from datetime import datetime, timedelta
import requests


class WhatsAppBot:
    def __init__(self, app, id_instance, api_token_instance, db):
        self.app = app
        self.id_instance = id_instance
        self.api_token_instance = api_token_instance
        self.db = db
        self.base_url = f"https://api.green-api.com/waInstance{self.id_instance}"
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=5)

    async def reboot_account(self):
        """Перезапуск аккаунта"""
        try:
            url = f"{self.base_url}/reboot/{self.api_token_instance}"
            response = await asyncio.get_event_loop().run_in_executor(
                self.executor,
                lambda: requests.get(url)
            )
            
            if response.status_code == 200:
                reboot_response = response.json()
                if reboot_response.get("isReboot"):
                    log_info("Аккаунт успешно перезапущен.")
                else:
                    log_error("Ошибка при перезапуске аккаунта.")
            else:
                log_error(f"Ошибка при запросе перезагрузки: статус {response.status_code}")

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
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:  # Если есть уведомление
                            receipt_id = data.get('receiptId')
                            body = data.get('body')  # Получаем тело уведомления
                            if body:  # Проверяем, что тело существует
                                with self.app.app_context():
                                    await self.process_webhook(body, receipt_id)  # Передаем body
                                    await self.delete_notification(receipt_id)
                            return True
        except Exception as e:
            log_error(f"Ошибка при получении уведомления: {str(e)}")
        return False
    
    async def delete_notification(self, receipt_id):
        """Удаление уведомления после обработки"""
        url = f"{self.base_url}/deleteNotification/{self.api_token_instance}/{receipt_id}"
        try:
            async with aiohttp.ClientSession() as session:
                await session.delete(url)
        except Exception as e:
            log_error(f"Ошибка при удалении уведомления: {str(e)}")

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
                await self.save_incoming_message(data, receipt_id)
            elif webhook_type == 'outgoingMessageStatus':
                # Сначала сохраняем сообщение, если его еще нет
                await self.save_outgoing_message_from_status(data, receipt_id)
                # Затем обновляем статус
                await self.update_message_status(data)
            elif webhook_type == 'outgoingAPIMessageReceived':
                await self.save_outgoing_message(data)
                
        except Exception as e:
            log_error(f"Ошибка обработки вебхука: {str(e)}")

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
                timestamp=timestamp
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
        log_info(f"WhatsApp бот запущен с ID: {self.id_instance}")

        await self.reboot_account()

        while self.running:
            try:
                if await self.receive_notification():
                    continue
                await asyncio.sleep(1)
            except Exception as e:
                log_error(f"Ошибка в цикле работы бота: {str(e)}")
                await asyncio.sleep(5)  # Используем await для асинхронного ожидания

    def stop(self):
        """Остановка бота"""
        self.running = False

    def __del__(self):
        """Закрываем пул потоков при удалении объекта"""
        self.executor.shutdown(wait=False)