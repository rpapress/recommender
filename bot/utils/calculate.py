from typing import List, Dict, Tuple
from statistics import median
from collections import defaultdict
from bot.db.models import Message


class Analytics:
    @staticmethod
    def analyze_response_times(messages: List[Message]) -> Dict:
        """
        Расчет времени ответа менеджера включая общее среднее время ответа.
        Группировка по менеджерам и их клиентам.
        """
        # Создаем структуру для хранения диалогов по менеджерам и клиентам
        conversations: Dict[str, Dict[str, List[Message]]] = defaultdict(lambda: defaultdict(list))
        
        for msg in messages:
            if msg.send_by_api:
                continue
                
            # Группируем сначала по менеджеру, потом по клиенту
            manager_id = msg.instance_wid
            client_id = msg.sender_chat_id
            conversations[manager_id][client_id].append(msg)

        response_analytics = {}
        all_response_times = []

        # Обрабатываем сообщения для каждого менеджера
        for manager_id, manager_conversations in conversations.items():
            manager_analytics = {}
            
            # Обрабатываем диалоги с каждым клиентом
            for client_id, msgs in manager_conversations.items():
                sorted_msgs = sorted(msgs, key=lambda x: x.timestamp)
                message_response_times = []
                last_client_msg = None

                for msg in sorted_msgs:
                    if msg.is_from_client:
                        last_client_msg = msg
                    else:
                        if last_client_msg:
                            response_time = (msg.timestamp - last_client_msg.timestamp).total_seconds()
                            minutes = response_time // 60
                            seconds = response_time % 60

                            message_data = {
                                # 'message_id': msg.id,
                                # 'client_sent_at': last_client_msg.timestamp.strftime('%a, %d %b %Y %H:%M:%S GMT'),
                                # 'manager_sent_at': msg.timestamp.strftime('%a, %d %b %Y %H:%M:%S GMT'),
                                'formatted_response_time': f"{int(minutes)}m {int(seconds)}s",
                                # 'response_time_in_seconds': response_time,
                                # 'client_contact_id': last_client_msg.sender_chat_id,
                                # 'manager_contact_id': msg.instance_wid,
                                'client_message': last_client_msg.message_text,
                                'manager_response': msg.message_text,
                                # 'sender_type_client': 'client',
                                # 'sender_type_manager': 'manager'
                            }

                            message_response_times.append(message_data)
                            all_response_times.append(response_time)
                            last_client_msg = None

                manager_analytics[client_id] = message_response_times

            response_analytics[manager_id] = manager_analytics

        # Добавляем общую статистику
        if all_response_times:
            avg_response_time = sum(all_response_times) / len(all_response_times)
            avg_minutes = int(avg_response_time // 60)
            avg_seconds = int(avg_response_time % 60)
            response_analytics['average_response_time'] = f"{avg_minutes}m {avg_seconds}s"
            response_analytics['total_messages'] = len(all_response_times)

        return response_analytics