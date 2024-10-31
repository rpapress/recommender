import json
import requests
import urllib.parse


def shorten_url(long_url):
    api_url = "https://twi.kz/api/v1/shorten"
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    data = {
        "url": long_url
    }

    response = requests.post(api_url, headers=headers, data=json.dumps(data))

    if response.status_code == 201:
        result = response.json()
        return result['shorten']
    else:
        print(f"Ошибка: {response.status_code}, {response.text}")
        return None


def encode_text_for_url(output_text):
    """
    Функция принимает текст, кодирует его для безопасной передачи в URL и возвращает закодированный текст.

    :param output_text: Текст, который нужно закодировать
    :return: Закодированный текст для использования в URL
    """
    return urllib.parse.quote(output_text, safe='')