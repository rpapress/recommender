import asyncio
import aiohttp
import time
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from bot.db.models import (
    Message,
    OutgoingMessageStatus, 
    ChatContext,
    RecommendedResponse
)
from bot.db.connect import db

from bot.settings.logger import log_info, log_error
from bot.controller.GreenAPI import GreenAPI
from bot.stack.traveler import interact_with_chatgpt_async


class WhatsAppBot:
    def __init__(self, app, id_instance, api_token_instance, db):
        self.app = app
        self.green_api = GreenAPI(app)
        self.id_instance = id_instance
        self.api_token_instance = api_token_instance
        self.db = db
        self.base_url = f"https://api.green-api.com/waInstance{self.id_instance}"
        self.running = True
        self.executor = ThreadPoolExecutor(max_workers=5)
        #? написать для этой переменной бекенд вместе с установленной компанией, 
        #? 1: ProfiDecor, ai: False
        #? 2: AkBaryus, ai: True
        self.ai_assistant = True

    async def schedule_reboot(self):
        """Планировщик перезапуска аккаунта каждые 8 часов"""
        while self.running:
            try:
                await self.green_api.reboot_account()
                # Ждем 8 часов
                await asyncio.sleep(8 * 60 * 60)  # 8 часов в секундах
            except Exception as e:
                log_error(f"Ошибка в планировщике перезапуска: {str(e)}")
                # В случае ошибки жду 5 минут и пробую снова
                await asyncio.sleep(300)

    async def get_or_create_context(self, chat_id):
        """Получение или создание контекста чата"""
        context = ChatContext.query.filter_by(chat_id=chat_id).first()
        if not context:
            context = ChatContext(chat_id=chat_id, messages=[])
            self.db.session.add(context)
            self.db.session.commit()
        return context

    async def update_context(self, chat_id, new_messages):
        """Обновление контекста чата"""
        context = await self.get_or_create_context(chat_id)
        context.messages = context.messages + new_messages
        
        # Ограничиваем количество сохраняемых сообщений для экономии токенов
        if len(context.messages) > 10:  # Храним последние 10 сообщений
            context.messages = context.messages[-10:]
            
        self.db.session.commit()

    async def save_recommended_response(self, message_id, client_phone_number, response_text):
        recommended_response = RecommendedResponse(
            message_id=message_id,
            client_phone_number=client_phone_number,
            response_text=response_text
        )
        self.db.session.add(recommended_response)
        self.db.session.commit()

    async def process_webhook(self, data, receipt_id):
        """Обработка входящего вебхука"""
        try:
            webhook_type = data.get('typeWebhook')
            if not webhook_type:
                return
            
            # log_info(f"Получен webhook типа: {webhook_type}, данные: {data}")

            if webhook_type == 'incomingMessageReceived':
                # Проверяем, является ли отправитель менеджером
                client = data.get('senderData', {}).get('sender')
                manager = data.get('instanceData', {}).get('wid')
                if client != manager:  # Если сообщение от клиента
                    await self.save_incoming_message(data, receipt_id)
                    
                    message_data = data.get('messageData', {})
                    message_text = (
                        message_data.get('textMessageData', {}).get('textMessage', '') or 
                        message_data.get('extendedTextMessageData', {}).get('text', '')
                    )
                    
                    message_text = json.loads(f'"{message_text}"') if message_text else ""

                    chat_id = data.get('senderData', {}).get('chatId')
                    
                    message = Message(
                        receipt_id=receipt_id,
                        is_from_client=True,
                        webhook_type=webhook_type,
                        sender_name=data.get('senderData', {}).get('senderName', ''),
                        sender_chat_id=chat_id,
                        instance_wid=manager,
                        message_type=message_data.get('typeMessage', 'text'),
                        message_text=message_text,
                        id_message=data.get('idMessage', ''),
                        instance_id=self.id_instance
                    )

                    self.db.session.add(message)
                    self.db.session.commit()
                    message_id = message.id
                    
                    try:
                        if self.ai_assistant:  # Если включен режим ИИ-ассистента
                            # Получаем контекст чата
                            context = await self.get_or_create_context(chat_id)
                            
                            # Генерация ответа с учетом контекста
                            ai_response = await interact_with_chatgpt_async(
                                message_text,
                                context.messages
                            )
                            # Обновляем контекст
                            new_messages = [
                                {"role": "user", "content": message_text},
                                {"role": "assistant", "content": ai_response}
                            ]
                            await self.update_context(chat_id, new_messages)
                            
                            # Отправляем ответ
                            await self.green_api.send_message(
                                chat_id=chat_id,
                                message=ai_response
                            )
                            log_info(f"Отправлен ответ ИИ в чат {chat_id}")
                        
                        else:  # Если ИИ-ассистент выключен
                            try:
                                # Генерация рекомендованного ответа с помощью ChatGPT
                                client_info = await self.green_api.get_contact_info(chat_id)
                                client_name = client_info.get('name', '') if client_info else ''
                                client_phone_number = data.get('senderData', {}).get('chatId', '')
                                if not client_name:
                                    client_name = "Клиент"

                                recommended_response = '[Рекомендованный ответ]'
                                # recommended_response = await interact_with_chatgpt_async(message_text)
                                # 1. сохраняю рекомендованный ответ
                                await self.save_recommended_response(message_id, client_phone_number, recommended_response)
                                # 2. #! Отправка рекомендованного ответа себе (менеджеру)
                                # await self.green_api.send_message(
                                #     chat_id=manager,
                                #     message=f'➡ {recommended_response}'
                                #     message=f'❇ Рекомендуемый ответ для: *{client_name}*\nНа сообщение: {message_text}\n➡ {recommended_response}'
                                # )
                                # log_info(f"Отправлен рекомендованный ответ менеджеру: {recommended_response}")
                            
                            except Exception as e:
                                log_error(f"Ошибка при генерации/отправке рекомендованного ответа: {str(e)}")
                    
                    except Exception as e:
                        log_error(f"Ошибка при генерации/отправке ответа: {str(e)}")
                            

            elif webhook_type == 'outgoingMessageStatus':
                chat_id = data.get('chatId')
                await self.save_outgoing_message_from_status(data, receipt_id)
                await self.update_message_status(data)

            #! Такого вебхука нет
            # elif webhook_type == 'outgoingAPIMessageReceived':
            #     await self.save_outgoing_message(data)
                
        except Exception as e:
            log_error(f"Ошибка обработки вебхука: {str(e)}")
    
    # --------------------------------------------------------------------------------------------------
    #? Получение уведомлений реализованно здесь из-за того что функция обработки вебхука находится здесь
    #? а я не хочу прыгать постоянно в файл GreenApi
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
                                        # именно тут этот вызов
                                        await self.process_webhook(body, receipt_id)
                                        await self.green_api.delete_notification(receipt_id)
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

    async def save_incoming_message(self, data, receipt_id):
        """Сохранение входящего сообщения"""
        try:
            manager_phone_from_data = data.get('instanceData', {}).get('wid')
            manager_info = await self.green_api.get_contact_info(manager_phone_from_data)
            manager_name = manager_info.get('name', '') if manager_info else ''
            client_phone_from_data = data.get('chatId', '')
            client_info = await self.green_api.get_contact_info(client_phone_from_data)

            client_name = client_info.get('name', '') if client_info else ''
            if not client_name:
                client_name = "Клиент"

            # Если имя пустое, присвою значение "Менеджер"
            if not manager_name:
                manager_name = "Менеджер"
                
            log_info(f'INSTANCEDATA={manager_name}')

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
                sender_name=f'Клиент: {client_name}',
                #! Сохрание имени менеджера в бд может быть пустым, это нормально 
                sender_contact_name=f'Менеджер: {manager_name}',
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
            manager_info = await self.green_api.get_contact_info(manager_phone_from_data)
            client_info = await self.green_api.get_contact_info(client_phone_from_data)
            
            # Получаю имя
            manager_name = manager_info.get('name', '') if manager_info else ''
            if not manager_name:
                manager_name = "Менеджер"
                
            client_name = client_info.get('name', '') if client_info else ''
            if not client_name:
                client_name = "Клиент"

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
            message_text = await self.green_api.get_message_text(
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
                sender_name=f'Клиент: {client_name}',
                sender_contact_name=f'Менеджер: {manager_name}',
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
            await self.green_api.reboot_account()

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
        if hasattr(self, 'executor') and self.executor:
            try:
                self.executor.shutdown(wait=False)
                log_info("Executor успешно завершен в __del__")
            except Exception as e:
                log_error(f"Ошибка при завершении работы executor в __del__: {str(e)}")