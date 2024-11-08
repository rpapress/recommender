import asyncio
import aiohttp
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from bot.db.models import (
    Message,
    OutgoingMessageStatus
)
from bot.settings.logger import log_info, log_error
from bot.controller.GreenAPI import GreenAPI


response_timers = {}
client_first_message_time = {}
# await self.green_api.delete_notification(receipt_id)

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

    async def process_webhook(self, data, receipt_id):
        
        print(f'')

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
                if client == manager:
                    # Если сообщение от менеджера, отменяем таймер для этого чата
                    chat_id = data.get('senderData', {}).get('chatId')
                    await self.cancel_response_timer({'chatId': chat_id})
                    log_info(f"Таймер отменен из-за ответа менеджера для чата {chat_id}")
                else:
                    # Если сообщение от клиента
                    await self.save_incoming_message(data, receipt_id)
                    await self.start_response_timer(data, receipt_id)

            elif webhook_type == 'outgoingMessageStatus':
                # Отменяем таймер при отправке сообщения менеджером
                chat_id = data.get('chatId')
                await self.cancel_response_timer({'chatId': chat_id})
                
                await self.save_outgoing_message_from_status(data, receipt_id)
                await self.update_message_status(data)
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
    
    async def start_response_timer(self, data, receipt_id):
        """Запуск таймера ожидания ответа менеджера"""
        sender_chat_id = data.get('senderData', {}).get('chatId')
        log_info(f'[start_response_timer] RECEIPTID={receipt_id}')
        
        if not sender_chat_id:
            log_error(f"Не удалось получить sender_chat_id из данных: {data}")
            return

        # Если нет времени первого сообщения для клиента, сохраняю его
        if sender_chat_id not in client_first_message_time:
            client_first_message_time[sender_chat_id] = datetime.now()

        # Если уже есть активный таймер для этого клиента, отменяю его
        if sender_chat_id in response_timers:
            response_timers[sender_chat_id].cancel()

        # Рассчитываю задержку с учетом первого сообщения
        first_message_time = client_first_message_time[sender_chat_id]
        time_elapsed = (datetime.now() - first_message_time).total_seconds()
        
        # Таймер продолжает отсчитывать от первого сообщения
        remaining_time = max(0, 420 - time_elapsed)  # задержка в 7 минут

        # Запускаю новый таймер
        timer = asyncio.create_task(self.send_scripted_message(receipt_id, sender_chat_id, data, delay=remaining_time))
        response_timers[sender_chat_id] = timer
        log_info(f"Запущен таймер ответа для клиента {sender_chat_id}, оставшееся время: {remaining_time} сек.")
        log_info(f"Текущий статус таймера для {sender_chat_id}: {response_timers.get(sender_chat_id, 'не найден')}")


    async def cancel_response_timer(self, data):
        """Отмена таймера, если менеджер ответил"""
        try:
            sender_chat_id = data.get('chatId')
            if sender_chat_id in response_timers:
                response_timers[sender_chat_id].cancel()
                del client_first_message_time[sender_chat_id]
                del response_timers[sender_chat_id]
                log_info(f"Таймер отменен для чата {sender_chat_id}")
        except Exception as e:
            log_error(f"Ошибка при отмене таймера: {str(e)}")

    async def send_scripted_message(self, receipt_id, sender_chat_id, data, delay):
        """Отправка заскриптованного сообщения после тайм-аута"""
        try:
            if not sender_chat_id:
                log_error("sender_chat_id is None, отправка сообщения невозможна")
                return
            
            await asyncio.sleep(delay)

            # Получаем информацию о контакте       
            contact_info = await self.green_api.get_contact_info(sender_chat_id)
            client_name = contact_info.get('name', '') if contact_info else ''
            if not client_name:
                client_name = "Клиент"
            
            log_info(f'CLIENTNAMEFROMSCRIPTER={client_name}')

            timestamp = data.get('timestamp', int(time.time()))
            # Преобразование Unix-времени в datetime
            timestamp = datetime.fromtimestamp(timestamp)
            
            # Повторная проверка перед отправкой
            if sender_chat_id not in response_timers:
                log_info(f"Таймер был отменен для {sender_chat_id}, отмена отправки сообщения")
                return
                
            log_info(f"Отправка заскриптованного сообщения клиенту {sender_chat_id}, так как ответа менеджера не поступило")
            
            chat_id = f"{sender_chat_id}"
            if not '@' in chat_id:
                chat_id = f"{sender_chat_id}@c.us"
                
            scripted_message = "Извините за задержку, менеджер скоро ответит."
            
            message = Message(
                receipt_id=receipt_id, 
                webhook_type='outgoing STATIC TEXT',
                sender_contact_name='static response',
                id_message=data.get('idMessage'),
                is_from_client=False,
                instance_id=data.get('instanceData', {}).get('idInstance'),
                instance_wid=data.get('instanceData', {}).get('wid'),
                # message_type=data.get('typeMessage'),
                sender_chat_id=sender_chat_id,
                sender_name=f'Клиент: {client_name}',
                message_text=scripted_message,  # Добавляю текст сообщения
                timestamp=timestamp
            )

            self.db.session.add(message)
            self.db.session.commit()
            
            await self.green_api.send_message(chat_id, scripted_message)
            
        except Exception as e:
            log_error(f"Ошибка при отправке заскриптованного сообщения: {str(e)}")
        
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
                sender_name=f'Клиент:{client_name}',
                sender_contact_name=f'Менеджер:{manager_name}',
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