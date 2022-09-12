import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv
from requests.exceptions import HTTPError
from telegram import Bot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='main.log',
    level=logging.DEBUG)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'main.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='UTF-8',
)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат по заданному ID чата."""
    logger.info('Старт отправки сообщения в Telegram')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение отправлено')
    except Exception:
        raise Exception('Ошибка отправки сообщения')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API Практикум.Домашка."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}

    logger.info('Старт запроса к API Практикум.Домашка')

    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise HTTPError('API возвратил ответ, отличный от 200')
    except HTTPError:
        raise HTTPError(
            f'Сбой в работе программы: Эндпоинт '
            f'https://practicum.yandex.ru/api/user_api/homework_statuses/ '
            f'недоступен. Код ответа API {homework_statuses.status_code}'
        )
    else:
        return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API Практикум.Домашка на корректность."""
    if not isinstance(response, dict):
        raise TypeError(
            'Тип данных в полученном ответе не соответствуют ожидаемым. '
            'Ответ API должен иметь тип "dict".'
        )
    if 'homeworks' not in response:
        raise KeyError(
            'В полученном ответе отсутсвует ключ со списком домашних работ.'
        )
    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'Тип данных в полученном ответе не соответствуют ожидаемым. '
            'Список домашних работ должен иметь тип "list".'
        )

    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if 'homework_name' not in homework:
        raise KeyError(
            'В полученной информации о домашней работе отсутствует '
            'ключ "homework_name".'
        )
    if 'status' not in homework:
        raise KeyError(
            'В полученной информации о домашней работе отсутствует '
            'ключ "status".'
        )

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_STATUSES:
        raise ValueError('Получен недокументированный статус домашней работы.')

    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    env_var = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    return all(env_var)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        message = (
            'Отсутствует одна или более переменных окружения. '
            'Программа остановлена.'
        )
        logger.critical(message)
        sys.exit(message)

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    prev_message = ''

    while check_tokens():
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework != []:
                message = parse_status(homework[0])
                if message != prev_message:
                    send_message(bot, message)
                    prev_message = message
                else:
                    logger.debug('Нет новых статусов домашней работы')
            current_timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(f'{error}')
            send_message(bot, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
