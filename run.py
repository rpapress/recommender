from flask import Flask
from flask_migrate import Migrate
from concurrent.futures import ThreadPoolExecutor
import time
from bot.settings.logger import log_info, log_error
from bot.controller.WhatsAppBot import WhatsAppBot
from bot.db.connect import db
from bot.settings.config import (
    DATABASE_USER,
    DATABASE_PASSWORD,
    DATABASE_HOST,
    DATABASE_PORT,
    DATABASE_NAME,
)


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ------------------------------------------
# Инициализация и миграции БД
db.init_app(app)
migrate = Migrate(app, db)
# ------------------------------------------

# ------------------------------------------
# работа в 3 потоках
executor = ThreadPoolExecutor(max_workers=3)
# ------------------------------------------

# ------------------------------------------
# инициализация классов
def start_bots():
    whatsappbot = WhatsAppBot(app)
    executor.submit(whatsappbot.run)
# ------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    start_bots()

    try:
        log_info('[run] Запуск всех компонентов..')
        print('[run] Запуск всех компонентов..')
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log_info("[STOP] Остановка ботов...")
        print("[STOP] Остановка ботов...")
        time.sleep(2)