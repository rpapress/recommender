import openai
import asyncio
from bot.settings.config import AI_API_KEY
from bot.settings.logger import log_info, log_error


class ChatGPTAssistant:
    SYSTEM_PROMPT = ("Ты профессиональная ассистент образовательного центра, вежливая и заботливая, тебя зовут Алтынай."
                "Твоя задача - помогать клиентам, отвечать на их вопросы и при необходимости "
                "перенаправлять к живому менеджеру.")
    
    def __init__(self, api_key: str):
        """Инициализация класса с указанием API ключа для доступа к OpenAI."""
        self.api_key = api_key
        openai.api_key = self.api_key
        self.messages = []

    def interact(self, prompt: str, context_messages: list) -> str:
        """Универсальная функция взаимодействия с ChatGPT."""
        try:
            messages = [self.system_message]
            messages.extend(context_messages)
            messages.append({"role": "user", "content": prompt})

            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=messages
            )
            tokens_used = response['usage']['total_tokens']
            print(f"Использовано токенов: {tokens_used}")
            
            assistant_reply = response.choices[0].message['content'].strip()
            return assistant_reply
        
        except Exception as e:
            return f"Ошибка при взаимодействии с моделью: {str(e)}"
        
            
    async def generate_ai_response(self, message_text: str, context_messages: list) -> str:
        """Генерация ответа с помощью ChatGPT с учетом контекста"""
        try:
            # Создаем копию контекста и добавляем новое сообщение
            messages = context_messages.copy()
            messages.append({"role": "user", "content": message_text})
            
            # Добавляем системное сообщение в начало для задания контекста
            system_message = {
                "role": "system",
                "content": "Ты - вежливый и профессиональный ассистент службы поддержки. " \
                          "Твоя задача - помогать клиентам, отвечать на их вопросы и при необходимости " \
                          "перенаправлять к живому менеджеру."
            }
            messages.insert(0, system_message)
            
            # Генерируем ответ
            response = await asyncio.to_thread(
                self.interact,
                message_text
            )
            
            return str(response)
        except Exception as e:
            # log_error(f"Ошибка генерации ответа ИИ: {str(e)}")
            print(f"Ошибка генерации ответа ИИ: {str(e)}")
            return "Извините, произошла ошибка. Наш менеджер скоро свяжется с вами."


async def interact_with_chatgpt_async(prompt: str, context_messages: list = None) -> str:
    """Асинхронная функция для взаимодействия с ChatGPT через класс ChatGPTAssistant."""
    if context_messages is None:
        context_messages = []
    assistant = ChatGPTAssistant(AI_API_KEY)
    response = await assistant.generate_ai_response(prompt, context_messages=[])
    return response

# ---------------------------------------------------------------------------------------------------------------
#* ChatGPTAssistant
# async def main():
#     while True:
#         prompt = input("Введите ваш вопрос (или 'выход' для завершения): ")
#         if prompt.lower() == 'выход':
#             print("Завершение программы.")
#             break
        
#         response = await interact_with_chatgpt_async(prompt)
#         print("Ответ:", response)

# if __name__ == "__main__":
#     asyncio.run(main())
# ---------------------------------------------------------------------------------------------------------------
