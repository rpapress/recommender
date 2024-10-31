import openai
import asyncio
from bot.settings.config import AI_API_KEY


class ChatGPTAssistant:
    def __init__(self, api_key: str):
        """Инициализация класса с указанием API ключа для доступа к OpenAI."""
        self.api_key = api_key
        openai.api_key = self.api_key
        self.messages = []

    def interact(self, prompt: str) -> str:
        """Универсальная функция взаимодействия с ChatGPT."""
        self.messages.append({"role": "user", "content": prompt})

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=self.messages
            )
            tokens_used = response['usage']['total_tokens']
            print(f"Использовано токенов: {tokens_used}")
            assistant_reply = response.choices[0].message['content'].strip()
            self.messages.append({"role": "assistant", "content": assistant_reply})

            return assistant_reply
        
        except Exception as e:
            return f"Ошибка при взаимодействии с моделью: {str(e)}"


async def interact_with_chatgpt_async(prompt: str) -> str:
    """Асинхронная функция для взаимодействия с ChatGPT через класс ChatGPTAssistant."""
    assistant = ChatGPTAssistant(AI_API_KEY)
    return await asyncio.to_thread(assistant.interact, prompt)

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