"""Bot for checking homework status by using Yandex Practicum API."""
import os
import logging
import requests
import sys
import time

import telegram

from dotenv import load_dotenv

load_dotenv()

hw_logger = logging.getLogger('ya_bot')
hw_logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = (logging.Formatter(
    '%(name)s - %(asctime)s - %(levelname)s - %(message)s'
))
handler.setFormatter(formatter)
hw_logger.addHandler(handler)

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


class SendMessageError(Exception):
    """Error while sending message."""

    pass


class APIResponseError(Exception):
    """API return uncorrect status code."""

    pass


class ResponseTypeError(Exception):
    """Wrong type in API response."""

    pass


class NoHomeworkError(Exception):
    """No homework to parse."""

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
        hw_logger.info(f'Отправка сообщения:{message}')
    except SendMessageError as error:
        hw_logger.error(f'Сбой при отправке сообщения:{error}')


def get_api_answer(current_timestamp):
    """Get answer from Yandex Practicum API."""
    api_answer = requests.get(
        url=ENDPOINT, headers=HEADERS,
        params={'from_date': current_timestamp or int(time.time())}
    )
    if api_answer.status_code != 200:
        raise APIResponseError(
            f'Эндпоинт недоступен. Код ответа: {api_answer.status_code}'
        )
    else:
        return api_answer.json()


def check_response(response):
    """Check response from Yandex Practicum API."""
    if isinstance(response, list):
        response = response[0]
    if not isinstance(response, dict):
        raise ResponseTypeError('В ответе API неверный тип данных')
    elif not response.get('homeworks'):
        raise KeyError('В ответе API нет ключа homeworks')
    elif not isinstance(response.get('homeworks'), list):
        raise ResponseTypeError(
            'В ответе API неверный тип данных по ключу homeworks'
        )
    else:
        return response.get('homeworks')


def parse_status(homework):
    """Parse homework from response of Yandex Practicum API."""
    if not homework:
        raise NoHomeworkError('Пустой аргумент в функции parse_status')
    elif not isinstance(homework, dict):
        raise ResponseTypeError(
            'В ответе API неверный тип данных по ключу homeworks'
        )
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('В ответе API нет ключа homework_name')
    homework_status = homework.get('status')
    if not homework_status:
        raise KeyError('В ответе API нет ключа homework_status')
    if homework_status not in HOMEWORK_STATUSES:
        raise HomeworkStatusError(
            f'Неожиданный статус домашней работы: {homework_status}'
        )
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Check if tokens load correctly."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for name, value in tokens.items():
        if not value:
            hw_logger.critical(
                f'Токен {name} отсутствует. Останавливаю программу.'
            )
            return False
    hw_logger.debug('Токены загрузились корректно.')
    return True


def log_and_message(bot, error):
    """Log errors and send error message to Telegram chat."""
    hw_logger.error(error, exc_info=True)
    send_message(bot=bot, message=error)


def main():
    """Do main bot logic."""
    if not check_tokens():
        hw_logger.critical(
            'Отсутствует одна или несколько из обязательных переменных.'
        )
        raise Exception

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status_cache = None

    while True:
        try:
            response = get_api_answer(bot, current_timestamp)
            homework = check_response(response)[0]
            if status_cache != homework['status']:
                status_cache = homework['status']
                message = parse_status(homework)
                send_message(bot, message)
            else:
                hw_logger.debug('Обновлений нет')
            current_timestamp = int(time.time())
            time.sleep(RETRY_TIME)
        except Exception as error:
            log_and_message(bot, f'Сбой в работе программы: {error}')
            time.sleep(RETRY_TIME)
        else:
            hw_logger.debug(
              'При отработке одного цикла программы исключений не возникло.')


if __name__ == '__main__':
    main()
