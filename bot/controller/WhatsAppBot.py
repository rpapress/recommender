import asyncio
import aiohttp
import os
from bot.db import db
from bot.utils.whatsApp_utils import WhatsAppBotUtils
from bot.models import (
    Client,
    Notification,
    ChatHistory
)
from bot.utils.speech_to_text import transcribe_audio
from bot.traveler import interact_with_chatgpt_async
from bot.controller.prompts import system_prompt, correct_form_prompt
from bot.controller.GreenAPI_controll import GreenAPI

from bot.utils.logger import log_info, log_error
from concurrent.futures import ThreadPoolExecutor


async def save_audio(download_url: str, file_name: str):
    """Сохранение аудиофайла на диск."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as response:
                if response.status == 200:
                    # Создаем папку для сохранения, если ее нет
                    os.makedirs('audio_files', exist_ok=True)
                    file_path = os.path.join('audio_files', file_name)

                    with open(file_path, 'wb') as f:
                        f.write(await response.read())
                    print(f'Аудиофайл сохранён: {file_path}')
                    log_info(f'Аудиофайл сохранён: {file_path}')
                else:
                    print(f'Ошибка при загрузке аудиофайла: {response.status}')
                    log_error(f'Ошибка при загрузке аудиофайла: {response.status}')
    except Exception as e:
        print(f'Исключение при сохранении аудиофайла: {e}')
        log_error(f'Исключение при сохранении аудиофайла: {e}')

async def handle_audio_message(message_data, sender_name):
    audio_data = message_data.get('fileMessageData', {})
    download_url = audio_data.get('downloadUrl')
    file_name = audio_data.get('fileName')
    print("Имя файла:", file_name)
    print(f"Получено аудиосообщение от {sender_name}")
    print("Скачиваем по URL:", download_url)

    log_info(f"Скачиваем по URL: {download_url}")
    log_info(f"Имя файла: {file_name}")
    log_info(f"Получено аудиосообщение от {sender_name}")

    await save_audio(download_url, file_name)
    file_path = os.path.join('audio_files', file_name)

    # Используем ThreadPoolExecutor для транскрипции
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        transcribed_text = await loop.run_in_executor(executor, transcribe_audio, file_path)

    if transcribed_text:
        text = transcribed_text
        print(f"Распознанный текст: {text}")
    else:
        text = 'Не удалось распознать аудиосообщение'

    return text
    
class WhatsAppBot:
    def __init__(self, app):
        self.app = app
        self.green_api = GreenAPI(app)
        self.blocklist = [
            '77775216269',
            '77054749947'
        ]

    async def process_message(self, message: dict):
        try:
            receipt_id = message.get('receiptId')
            sender_data = message.get('body', {}).get('senderData', {})
            message_data = message.get('body', {}).get('messageData', {})
            print()
            print()
            print(message_data)
            print()
            print()

            phone_number = sender_data.get('chatId')[:-5]

            if phone_number in self.blocklist:
                print(f"Сообщение от {phone_number} заблокировано, оно не будет обработано.")
                log_info(f"[BLOCKLIST] Сообщение от {phone_number} заблокировано, оно не будет обработано.")
                await self.green_api.delete_notification(receipt_id)
                return
            
            sender_name = sender_data.get('chatName') or sender_data.get('senderContactName', 'Unknown')
            message_type = message_data.get('typeMessage')

            text = None
            if message_type == 'textMessage':
                text = message_data.get('textMessageData', {}).get('textMessage')
                print(f"Получено текстовое сообщение от {sender_name}: {text}")
            
            elif message_type == 'extendedTextMessage':
                # если это расширенное текстовое сообщение
                text = message_data.get('extendedTextMessageData', {}).get('text')
                print(f"Получено расширенное текстовое сообщение от {sender_name}: {text}")
                log_info(f"Получено расширенное текстовое сообщение от {sender_name}: {text}")
            
            elif message_type == 'audioMessage':
                text = await handle_audio_message(message_data, sender_name)
            else:
                print(f"Неизвестный тип сообщения от {sender_name}: {message_type}")
                text = None


            print("Текст после обработки:", text)
            if text is None:
                print("Текст сообщения отсутствует")
                log_info("Текст сообщения отсутствует")
                await self.green_api.delete_notification(receipt_id)
                return
            
            with self.app.app_context():
                client = Client.query.filter_by(phone_number=phone_number).first()
                if not client:
                    client = Client(
                        phone_number=phone_number,
                        name_in_whatsapp=sender_name,
                        source='WhatsApp',
                        first_message=text,
                        language='kz'
                    )
                    db.session.add(client)
                    db.session.commit()
                else:
                    if text.lower() in ["/очистить контекст", "/забудь контекст", "/delete_context", "/rsm"]:
                        await WhatsAppBotUtils.clear_context(self.green_api, client)
                        #! изменить
                        await self.green_api.delete_notification(receipt_id)
                        log_info(f'Сброс контекста для клиента {phone_number}')
                        return
                    
                await WhatsAppBotUtils.save_notification(receipt_id, client.phone_number, text)

                chat_history = ChatHistory.query.filter_by(phone_number=client.phone_number).all()
                context = "\n".join([f"{entry.user_message}\n{entry.gpt_response}" for entry in chat_history])
                
                log_info(f'[CHAT HISTORY] История чата клиента: {phone_number}\n{chat_history}')
                print()
                log_info(f'[FULL CONTEXT] Полный контекст с клиентом: {phone_number}\n{context}')

                try:
                    # BASE REQUEST/RESPONSE
                    response_text = await interact_with_chatgpt_async(system_prompt + context + " " + text)
                except Exception as Err:
                    print(f'[AI ERROR] {Err}')
                    response_text = "Извините, произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте еще раз позже."
                
                chat_history_entry = ChatHistory(
                    phone_number=client.phone_number,
                    user_message=text,
                    gpt_response=response_text
                )
                db.session.add(chat_history_entry)
                db.session.commit()
                print(response_text.startswith("Конечно"))
                print(f'[TEXXXETTTT] {response_text}')
                    # Здесь я проверяю анкету, чтобы отправить
                check_send_form = await interact_with_chatgpt_async(f"Выступи в роли эксперта по анализу текста. На основе предоставленного текста {response_text} проверь, содержится ли 5 символов двоеточия ':' в тексте. Твой ответ должен содержать: 'True' или 'False'. Никогда не давай другие ответы.")
                log_info(f'[Найдено 5 двоеточий] {check_send_form} в тексте: {response_text}')
                print(f'[Найдено 5 двоеточий] {check_send_form}')

                if check_send_form.strip() == 'True' and client.status == 'не отвечен':
                    log_info('[Отправка менеджеру..]')
                    client.status = 'success'
                    # ---
                    # send manager
                    correct_form_send_manager = await interact_with_chatgpt_async(correct_form_prompt + response_text)
                    await WhatsAppBotUtils.send_to_manager(self.green_api, correct_form_send_manager)
                    # await WhatsAppBotUtils.clear_context(client)
                    # ---

                    db.session.commit()
                    print(f'Cтатус клиента поменялся на "success"')
                    log_info(f'Cтатус клиента поменялся на "success"')
                else:
                    print(f'Cтатус клиента остается "не отвечен".')
                    log_info(f'Cтатус клиента остается "не отвечен".')

                await self.green_api.send_message(client.phone_number, response_text)
                await self.green_api.delete_notification(receipt_id)

        except Exception as e:
            print(f"Ошибка при обработке сообщения: {e}")
            log_error(f'Ошибка в процессе обработки сообщения: {e}')


    async def start_receiving(self):
        """Цикл для постоянного получения сообщений через API"""
        while True:
            print('[start_receiving] получение сообщений через API')
            messages = await self.green_api.get_messages()
            if messages:
                await self.process_message(messages)
            await asyncio.sleep(2)

    def run(self):
        print('[run] запуск полученных')
        asyncio.run(self.start_receiving())