import os
from dotenv import load_dotenv


load_dotenv()
USER_INSTAGRAM = os.getenv('USER_INSTAGRAM')
PASSWORD_INSTAGRAM = os.getenv("PASSWORD_INSTAGRAM")
DATABASE_USER = os.getenv('DATABASE_USER')
DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
DATABASE_NAME = os.getenv('DATABASE_NAME')
DATABASE_HOST = os.getenv('DATABASE_HOST')
DATABASE_PORT = os.getenv('DATABASE_PORT')

GREEN_API_URL = os.getenv('GREEN_API_URL')
GREEN_API_ID = os.getenv('GREEN_API_ID')
GREEN_API_TOKEN = os.getenv('GREEN_API_TOKEN')

AI_API_KEY = os.getenv("AI_API_KEY")
