import asyncio
import aiohttp
import os
from bot.db.connect import db
from bot.utils.whatsApp_utils import WhatsAppBotUtils
from bot.db.models import (
    Client,
    ChatHistory,
)
from bot.stack.traveler import interact_with_chatgpt_async
from bot.stack.prompts import system_prompt, correct_form_prompt
from bot.controller.GreenAPI_controll import GreenAPI
from bot.settings.logger import log_info, log_error
from concurrent.futures import ThreadPoolExecutor
from bot.settings.config import MANAGER_PHONE_NUMBER
from bot.utils.create_link import encode_text_for_url, shorten_url
from datetime import datetime, timedelta


RECOMMENDER = False

class WhatsAppBot:
    def __init__(self, app):
        self.app = app
        self.green_api = GreenAPI(app)
        self.last_outgoing_status_time = datetime.now()
        self.pending_ai_responses = {}  # Store pending responses by chat_id

    async def process_message(self, message: dict):
        try:
            receipt_id = message.get('receiptId')
            body = message.get('body', {})
            instance_data = body.get('instanceData', {})
            status = body.get('status')
            timestamp = body.get('timestamp')
            message_id = body.get('idMessage')
            send_by_api = body.get('sendByApi', False)
            chat_id = body.get('senderData', {}).get('chatId', '')
            print(f'CHAT ID ............ ========= [{chat_id}]')
            client_phone_number = body.get('senderData', {}).get('chatId', '').replace('@c.us', '')
            manager_phone_number = instance_data.get('wid', '').replace('@c.us', '')
            print(f'[client phone number] {client_phone_number}')
            print(f'[manager phone number] {manager_phone_number}')
            
            # имя отправителя
            sender_name = body.get('senderData', {}).get('chatName') or body.get('senderData', {}).get('senderContactName', 'Unknown')
            
            # тип сообщения
            message_type = body.get('typeWebhook')

            text = None
            if message_type == 'incomingMessageReceived':
                print(f'Входящее сообщение от клиента {client_phone_number}')
                log_info(f'Входящее сообщение от клиента {client_phone_number}')

                message_data = body.get('messageData', {})
                if message_data.get('typeMessage') == 'textMessage':
                    text = message_data.get('textMessageData', {}).get('textMessage')
                elif message_data.get('typeMessage') == 'extendedTextMessage':
                    text = message_data.get('extendedTextMessageData', {}).get('text')
                elif message_data.get('typeMessage') == 'imageMessage':
                    image_url = message_data.get('imageMessageData', {}).get('url')
                    print(f"Получено изображение: {image_url}")

                await self.green_api.delete_notification(receipt_id)

            elif message_type == 'outgoingMessageStatus':
                print('Сообщение отправлено клиенту')
                status = body.get('status')
                log_info(f"Получено статус сообщения: {status}")
                if status == 'sent':
                    with self.app.app_context():
                        manager = Client.query.filter_by(phone_number=manager_phone_number).first()
                        if not manager:
                            manager = Client(
                                phone_number=manager_phone_number,
                                name_in_whatsapp=sender_name,
                                source='WhatsApp',
                                first_message=text,
                                language='kz',
                                role_manager=True
                            )
                            db.session.add(manager)
                            db.session.commit()

                        await WhatsAppBotUtils.save_notification(
                            receipt_id=receipt_id,
                            phone_number=manager_phone_number,
                            message_text='text',
                            message_type=message_type,
                            message_id=message_id,
                            send_by_api=False,
                            received_at=timestamp,
                        )
                    await self.green_api.delete_notification(receipt_id)
                    return
            
                # if status == 'sent':
                #     print(receipt_id)
                #     print()
                    # data_message = await self.green_api.get_message(chat_id, message_id)
                    # await self.green_api.send_message(MANAGER_PHONE_NUMBER, data_message)
                    
                    # log_info(f'[DATA_MESSAGE] {data_message}')
                    # print(f'[DATA_MESSAGE] {data_message}')

                    # логика получения сообщения по id от менеджера
                    # сохранение в бд
                    # и удалять уведомления от менеджера

                elif status == 'delivered' or status == 'read':
                    log_info(f"Удаление ненужного сообщения {receipt_id}")
                    print(f"Удаление ненужного сообщения {receipt_id}")
                    await self.green_api.delete_notification(receipt_id)



            if text is None:
                print("Текст сообщения отсутствует")
                log_info("Текст сообщения отсутствует")
                await self.green_api.delete_notification(receipt_id)
                return
            

            with self.app.app_context():
                #* SAVE CLIENT
                client = Client.query.filter_by(phone_number=client_phone_number).first()
                if not client:
                    client = Client(
                        phone_number=client_phone_number,
                        name_in_whatsapp=sender_name,
                        source='WhatsApp',
                        first_message=text,
                        language='kz',
                        role_manager=False
                    )
                    db.session.add(client)
                    db.session.commit()
                else:
                    if text.lower() in ["/очистить контекст", "/забудь контекст", "/delete_context", "/rsm"]:
                        await WhatsAppBotUtils.clear_context(self.green_api, client)
                        #! изменить
                        await self.green_api.delete_notification(receipt_id)
                        log_info(f'Сброс контекста для клиента {client_phone_number}')
                        return
                #* SAVE CLIENT

                #* SAVE NOTIFICATION
                await WhatsAppBotUtils.save_notification(
                    receipt_id=receipt_id,
                    phone_number=client_phone_number,
                    message_text=text,
                    message_type=message_type,
                    message_id=message_id,
                    send_by_api=send_by_api,
                    received_at=timestamp,
                )
                #* SAVE NOTIFICATION

    
                #? CONTEXT
                # # дата для контекста два дня назад
                # three_days_ago = datetime.now() - timedelta(days=2)
                # # фильтрую записи чата по номеру телефона и дате за последние три дня
                # chat_history = ChatHistory.query.filter(
                #     ChatHistory.phone_number == client.phone_number,
                #     ChatHistory.timestamp >= three_days_ago
                # ).all()

                # context = "\n".join([f"{entry.user_message}\n{entry.gpt_response}" for entry in chat_history])
                # log_info(f'[CHAT HISTORY] История чата клиента: {client_phone_number}\n{chat_history}')
                # print()
                # log_info(f'[FULL CONTEXT] Полный контекст с клиентом: {client_phone_number}\n{context}')
                #? CONTEXT

                # try:
                #     # BASE REQUEST/RESPONSE
                #     response_text = await interact_with_chatgpt_async(system_prompt + context + " " + text)
                # except Exception as Err:
                #     print(f'[AI ERROR] {Err}')
                #     response_text = "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз позже."
                #! ---
                response_text = '[Здесь должно быть сообщение от ChatGPT]'
                #! ---


                chat_history_entry = ChatHistory(
                    phone_number=client_phone_number,
                    user_message=text,
                    gpt_response=response_text
                )
                db.session.add(chat_history_entry)
                db.session.commit()

                #* рекомендатор
                # encoded_text = encode_text_for_url(response_text)
                # split_url = f"https://api.whatsapp.com/send?phone={client_phone_number}&text={encoded_text}"
                # short_url = shorten_url(split_url)
                # result = f"❇️ Рекомендуемый ответ для: *{sender_name}* ({client_phone_number})\nНа сообщение: {text}\n➡️ *Кликните:* {short_url}"
                # db.session.add(chat_history_entry)
                # db.session.commit()
                #* рекомендатор


                #? в случае отключения рекомендатора поменять result на response_text от ChatGPT

                if chat_id:
                    if RECOMMENDER:
                        await self.green_api.send_message(MANAGER_PHONE_NUMBER, '[заглушка] рекомендованный ответ от ИИ в лс менеджеру')
                    else:
                        await self.green_api.send_message(client_phone_number, '[заглушка] ответ от ии')


        except Exception as e:
            print(f"Ошибка при обработке сообщения: {e}")
            log_error(f'Ошибка в процессе обработки сообщения: {e}')


    async def check_and_send_pending_responses(self):
        """Check and send pending AI responses if 15 seconds have passed since last status message."""
        current_time = datetime.now()
        time_since_last_status = (current_time - self.last_outgoing_status_time).total_seconds()
        
        if time_since_last_status >= 15:  # 15 seconds threshold
            # Send all pending responses
            for chat_id, data in list(self.pending_ai_responses.items()):  # Use list to avoid runtime modification issues
                if RECOMMENDER:
                    await self.green_api.send_message(MANAGER_PHONE_NUMBER, '[заглушка] рекомендованный ответ от ИИ в лс менеджеру')
                else:
                    await self.green_api.send_message(data['client_phone'], data['response'])
                
                # Remove sent response from pending queue
                del self.pending_ai_responses[chat_id]
                print(f"Sent delayed AI response to {data['client_phone']}")


    async def start_receiving(self):
        """Цикл для постоянного получения сообщений через API"""
        while True:
            print('[start_receiving] получение сообщений через API')
            messages = await self.green_api.get_messages()
            if messages:
                await self.process_message(messages)
            await asyncio.sleep(2)

    def run(self):
        print('[WhatsAppBot] запуск полученных')
        asyncio.run(self.start_receiving())