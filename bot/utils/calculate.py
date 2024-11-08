from typing import List, Dict, Tuple
from statistics import median
from collections import defaultdict

from bot.db.models import Message


from typing import List, Dict, Tuple
from datetime import datetime

from typing import List, Dict, Tuple
from datetime import datetime


from typing import List, Dict, Tuple
from datetime import datetime

class Analytics:
    @staticmethod
    def analyze_response_times(messages: List[Message]) -> Dict[str, List[Dict[str, float]]]:
        """
        Расчет времени ответа менеджера для каждого полученного и отправленного сообщения.
        Время ответа представляется в формате 'минуты:секунды'.
        """
        conversations: Dict[Tuple[str, str], List[Message]] = {}

        for msg in messages:
            if msg.send_by_api:
                continue

            conversation_key = (msg.sender_chat_id, msg.instance_wid)

            if conversation_key not in conversations:
                conversations[conversation_key] = []
            conversations[conversation_key].append(msg)

        response_analytics = {}

        for (client_id, manager_id), msgs in conversations.items():
            sorted_msgs = sorted(msgs, key=lambda x: x.timestamp)

            # Храним данные для каждого сообщения
            message_response_times = []

            last_client_msg = None

            for msg in sorted_msgs:
                if msg.is_from_client:
                    last_client_msg = msg
                else:
                    if last_client_msg:
                        # Расчет времени ответа менеджера на сообщение клиента
                        response_time = (msg.timestamp - last_client_msg.timestamp).total_seconds()

                        # Преобразуем время ответа в минуты и секунды
                        minutes = response_time // 60
                        seconds = response_time % 60

                        message_data = {
                            'message_id': msg.id,
                            'client_message_timestamp': last_client_msg.timestamp.strftime('%a, %d %b %Y %H:%M:%S GMT'),
                            'manager_message_timestamp': msg.timestamp.strftime('%a, %d %b %Y %H:%M:%S GMT'),
                            'response_time': f"{int(minutes)}m {int(seconds)}s",
                            'client_phone': last_client_msg.sender_chat_id,  # Номер телефона клиента
                            'manager_phone': msg.instance_wid,  # Номер телефона менеджера
                            'client_message_text': last_client_msg.message_text,  # Текст сообщения клиента
                            'manager_message_text': msg.message_text,  # Текст сообщения менеджера
                            'client_sender': 'client',  # Роль отправителя (клиент)
                            'manager_sender': 'manager'  # Роль отправителя (менеджер)
                        }

                        # Сохраняем время ответа для этого сообщения
                        message_response_times.append(message_data)

                        # После обработки ответа менеджера сбрасываем информацию о клиентском сообщении
                        last_client_msg = None

            response_analytics[manager_id] = message_response_times

        return response_analytics
