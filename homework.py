"""Bot for checking homework status by using Yandex Practicum API."""
import logging
import os
import requests
import sys
import time

import telegram
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger('ya_bot')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter(
    '%(name)s - %(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEVORK_VERDICT = {
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
        logger.info(f'Отправлено сообщение:{message}')
    except SendMessageError as error:
        logger.error(f'Сбой при отправке сообщения:{error}', exc_info=True)


def get_api_answer(current_timestamp):
    """Get answer from Yandex Practicum API."""
    api_answer = requests.get(
        url=ENDPOINT, headers=HEADERS,
        params={'from_date': current_timestamp}
    )
    if api_answer.status_code != 200:
        raise APIResponseError(
            f'Некорректный ответ сервера. '
            f'Код ответа: {api_answer.status_code}, '
            f'URL = {ENDPOINT}, HEADERS = {HEADERS}, '
            f'Параметры запроса: form_date = {current_timestamp}'
        )
    print(api_answer)
    return api_answer.json()


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
    if 'homework_status' not in homework:
        raise KeyError('В ответе API нет ключа homework_status')
    status = homework['homework_status']
    if status not in HOMEVORK_VERDICT:
        raise HomeworkStatusError(
            f'Неожиданный статус домашней работы: {status}'
        )
    verdict = HOMEVORK_VERDICT.get(status)
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
        raise Exception

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    status_cache = None

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)[0]
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
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
