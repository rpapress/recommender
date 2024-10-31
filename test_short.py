import requests
import urllib.parse
import json


manager_phone = '77759419359'
service_type_select = 'Беззалоговый кредит'


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

    if response.status_code == 201:  # 201 Created
        result = response.json()
        return result['shorten']
    else:
        print(f"Ошибка: {response.status_code}, {response.text}")
        return None


 # Базовый текст
base_text = f"Здравствуйте! Я хочу получить бесплатную консультацию по услуге - {service_type_select}"
# Кодирование текста в формат URL
encoded_text = urllib.parse.quote(base_text)
# Формирование ссылки
manager_url_for_client = f"https://api.whatsapp.com/send?phone={manager_phone}&text={encoded_text}"
new_manager_url_for_client = shorten_url(manager_url_for_client)
print(new_manager_url_for_client)