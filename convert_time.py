import datetime


def convert_timestamp_to_readable(timestamp):
    """
    Преобразует Unix timestamp в читаемую дату и время.

    :param timestamp: Unix timestamp
    :return: Читаемая строка с датой и временем
    """
    # Используем timezone.utc для указания временной зоны
    readable_date = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    return readable_date

# Пример использования
if __name__ == "__main__":
    # Пример timestamp
    timestamp = 1730283921
    readable_date = convert_timestamp_to_readable(timestamp)
    
    print(f"Timestamp: {timestamp} -> Читаемая дата и время: {readable_date}")
