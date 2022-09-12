import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv
from telegram import Bot
from telegram.ext import CommandHandler, Updater

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
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение отправлено')
    except Exception as error:
        logger.error(f'{error}')
        raise Exception('Ошибка отправки сообщения')


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API Практикум.Домашка.
    В качестве параметра функция получает временную метку.
    В случае успешного запроса должна вернуть ответ API,
    преобразовав его из формата JSON к типам данных Python."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}

    homework_statuses = requests.get(
        ENDPOINT,
        headers=HEADERS,
        params=params
    )
    if homework_statuses.status_code == 200:
        return homework_statuses.json()
    else:
        logger.error(
            f'Сбой в работе программы: Эндпоинт '
            f'https://practicum.yandex.ru/api/user_api/homework_statuses/ '
            f'недоступен. Код ответа API {homework_statuses.status_code}'
        )
        raise Exception(
            f'Сбой в работе программы: Эндпоинт '
            f'https://practicum.yandex.ru/api/user_api/homework_statuses/ '
            f'недоступен. Код ответа API {homework_statuses.status_code}'
        )


def check_response(response):
    """Проверяет ответ API Практикум.Домашка на корректность."""
    if not isinstance(response, dict):
        logger.error(
            'Тип данных в полученном ответе не соответствуют ожидаемым. '
            'Ответ API должен иметь тип "dict".'
        )
        raise TypeError(
            'Тип данных в полученном ответе не соответствуют ожидаемым. '
            'Ответ API должен иметь тип "dict".'
        )
    if not isinstance(response['homeworks'], list):
        logger.error(
            'Тип данных в полученном ответе не соответствуют ожидаемым. '
            'Список домашних работ должен иметь тип "list".'
        )
        raise TypeError(
            'Тип данных в полученном ответе не соответствуют ожидаемым. '
            'Список домашних работ должен иметь тип "list".'
        )
    if 'homeworks' not in response:
        logger.error(
            'В полученном ответе отсутсвует ключ со списком домашних работ'
        )
        raise KeyError(
            'В полученном ответе отсутсвует ключ со списком домашних работ'
        )
    if response['homeworks'] == []:
        logger.error('Получен пустой список домашних работ')
        raise ValueError('Получен пустой список домашних работ')
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    homework_name = homework['homework_name']
    homework_status = homework['status']

    if (
        homework_status not in HOMEWORK_STATUSES
        and homework_status is not None
    ):
        logger.error('Получен недокументированный статус домашней работы')
        raise ValueError('Получен недокументированный статус домашней работы')
    elif homework_status is not None:
        verdict = HOMEWORK_STATUSES[homework_status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        return None


def check_tokens():
    """Проверяет доступность переменных окружения, которые
    необходимы для работы программы."""
    env_var_list = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if all(env_var_list):
        return True
    else:
        return False


def wake_up(update, context):
    chat = update.effective_chat
    name = update.message.chat.first_name
    context.bot.send_message(chat_id=chat.id,
                             text=f'Спасибо, что включили меня, {name}')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствует одна или более переменных окружения')

    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    updater = Updater(token=TELEGRAM_TOKEN)
    # updater.dispatcher.add_handler(CommandHandler('start', wake_up))

    prev_message = ''

    while check_tokens():
        try:
            # updater = Updater(token=TELEGRAM_TOKEN)
            updater.dispatcher.add_handler(CommandHandler('start', wake_up))
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
            message = parse_status(homework)
            if message != prev_message and message is not None:
                send_message(bot, message)
                prev_message = message
            else:
                logger.debug('Нет новых статусов домашней работы')
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
