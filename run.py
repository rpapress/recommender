from flask import Flask
from flask_migrate import Migrate
from concurrent.futures import ThreadPoolExecutor
import time
import sys
import signal
import asyncio
from bot.settings.logger import log_info, log_error
from bot.db.connect import db
from bot.controller.WhatsAppBot import WhatsAppBot
from bot.db.models import Message, OutgoingMessageStatus, BotCounter
from bot.settings.config import (
    DATABASE_USER,
    DATABASE_PASSWORD,
    DATABASE_HOST,
    DATABASE_PORT,
    DATABASE_NAME,
    GREEN_API_ID,
    GREEN_API_TOKEN
)


class Application:
    def __init__(self):
        self.app = Flask(__name__)
        self.configure_app()
        self.executor = ThreadPoolExecutor(max_workers=3)
        # добавление нескольктх ботов
        self.bots = []
        self.running = True
        
    def configure_app(self):
        """Конфигурация Flask приложения"""
        self.app.config['SQLALCHEMY_DATABASE_URI'] = (
            f"postgresql://{DATABASE_USER}:{DATABASE_PASSWORD}"
            f"@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_NAME}"
        )
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Инициализация БД и миграций
        db.init_app(self.app)
        self.migrate = Migrate(self.app, db)
        
    def init_database(self):
        """Инициализация базы данных"""
        try:
            with self.app.app_context():
                db.create_all()
                log_info("База данных успешно инициализирована")
        except Exception as e:
            log_error(f"Ошибка инициализации базы данных: {e}")
            sys.exit(1)
            
    def start_bots(self):
        """Запуск всех ботов"""
        try:
            whatsapp_bot = WhatsAppBot(
                self.app,
                id_instance=GREEN_API_ID,
                api_token_instance=GREEN_API_TOKEN,
                db=db
            )
            self.bots.append(whatsapp_bot)
            self.executor.submit(asyncio.run, whatsapp_bot.run())
            log_info(f"WhatsApp бот успешно запущен с ID: {GREEN_API_ID}")
        except Exception as e:
            log_error(f"Ошибка запуска WhatsApp бота: {e}")
            self.shutdown()
            
    def shutdown(self):
        """Корректное завершение работы приложения"""
        self.running = False
        log_info("Начинаем остановку приложения...")
        
        # Остановка всех ботов
        for bot in self.bots:
            try:
                if hasattr(bot, 'stop'):
                    bot.stop()
            except Exception as e:
                log_error(f"Ошибка при остановке бота: {e}")
        
        # Завершение пула потоков
        self.executor.shutdown(wait=True)
        log_info("Приложение успешно остановлено")
        sys.exit(0)
        
    def run(self):
        """Основной метод запуска приложения"""
        try:
            self.init_database()
            self.start_bots()
            log_info("Приложение успешно запущено")

            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.shutdown()

if __name__ == '__main__':
    application = Application()
    application.run()