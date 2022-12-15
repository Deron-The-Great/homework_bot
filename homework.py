"""Bot for checking homework status by using Yandex Practicum API."""
import json
import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from logging.handlers import RotatingFileHandler

load_dotenv()

logger = logging.getLogger('ya_bot')
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('main.log', maxBytes=50000000, backupCount=5)
formatter = logging.Formatter(
    '%(name)s - %(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class TokenError(Exception):
    """Error while loading tokens."""

    pass


class SendMessageError(Exception):
    """Error while sending message."""

    pass


class APIResponseError(Exception):
    """API return uncorrect status code."""

    pass


class ResponseTypeError(Exception):
    """Wrong type in API response."""

    pass


class RequestError(Exception):
    """Can't do request to API."""

    pass


class JSONError(Exception):
    """Can't read JSON."""

    pass


class HomeworkStatusError(Exception):
    """Unexpected homework status in API response."""

    pass


def send_message(bot, message):
    """Send message to me in Telegram."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.info(f'Успешно тправлено сообщение:{message}')
    except SendMessageError as error:
        logger.error(f'Сбой при отправке сообщения:{error}', exc_info=True)


def get_api_answer(timestamp):
    """Get answer from Yandex Practicum API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            url=ENDPOINT, headers=HEADERS, params=params
        )

        if response.status_code != HTTPStatus.OK:
            raise Exception
    except requests.exceptions.RequestException:
        raise RequestError('Не удалось обратиться к API Яндекс Практикума.')
    try:
        return response.json()
    except json.JSONDecodeError:
        raise JSONError(
            'Ответ не удалось привести к стандартным объектам Python'
        )


def check_response(response):
    """Check response from Yandex Practicum API."""
    print(response)
    if isinstance(response, list):
        response = response[0]
    if not isinstance(response, dict):
        raise ResponseTypeError('В ответе API неверный тип данных')
    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа homeworks')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise ResponseTypeError(
            'В ответе API неверный тип данных по ключу homeworks'
        )
    return homeworks


def parse_status(homework):
    """Parse homework from response of Yandex Practicum API."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе API нет ключа homework_name')
    name = homework['homework_name']
    if 'status' not in homework:
        raise KeyError('В ответе API нет ключа homework_status')
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise HomeworkStatusError(
            f'Неожиданный статус домашней работы: {status}'
        )
    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{name}". {verdict}'


def check_tokens():
    """Check if tokens load correctly."""
    is_correct = True
    for name in ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']:
        if globals()[name] is None:
            logger.critical(
                f'Токен {name} отсутствует. Программа отсановлена.'
            )
            is_correct = False
    logger.debug('Токены загрузились корректно.')
    return is_correct


def main():
    """Do main bot logic."""
    if not check_tokens():
        logger.critical(
            'Отсутствует одна или несколько из обязательных переменных.'
        )
        raise TokenError

    logger.info('Бот начал работу')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 0
    status_cache = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                if status_cache != homework['status']:
                    message = parse_status(homework)
                    send_message(bot, message)
                    status_cache = homework['status']
                else:
                    logger.debug('Обновлений нет')
                current_timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)
            send_message(bot=bot, message=message)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
