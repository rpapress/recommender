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
            message_text = message_data.get('extendedTextMessageData', {}).get('text', '')

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
            )
            
            self.db.session.add(message)
            self.db.session.commit()
            log_info(f"Сохранено входящее сообщение: {message.id}")
            
        except Exception as e:
            log_error(f"Ошибка сохранения входящего сообщения: {str(e)}")
            self.db.session.rollback()

    async def save_outgoing_message(self, data):
        """Сохранение исходящего сообщения"""
        try:
            message_data = data.get('messageData', {})
            message = Message(
                receipt_id=data.get('receiptId'),
                webhook_type='outgoing',
                id_message=data.get('idMessage'),
                is_from_client=False,
                instance_id=self.id_instance,
                instance_wid=data.get('instanceData', {}).get('wid', ''),
                message_type=message_data.get('typeMessage'),
                message_text=message_data.get('textMessageData', {}).get('textMessage')
            )
            
            self.db.session.add(message)
            self.db.session.commit()
            log_info(f"Сохранено исходящее сообщение: {message.id}")
            
        except Exception as e:
            log_error(f"Ошибка сохранения исходящего сообщения: {str(e)}")
            self.db.session.rollback()

    async def update_message_status(self, data):
        """Обновление статуса сообщения"""
        try:
            status = OutgoingMessageStatus(
                message_id=data.get('idMessage'),
                chat_id=data.get('chatId'),
                status=data.get('status'),
                send_by_api=True
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