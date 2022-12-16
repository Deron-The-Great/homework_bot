"""Bot for checking homework status by using Yandex Practicum API."""
import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv
from telegram.error import TelegramError

import custom_exceptions as exceptions

load_dotenv()

logger = logging.getLogger('ya_bot')
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    __file__ + '.log',
    maxBytes=50000000,
    backupCount=5
)
formatter = logging.Formatter(
    '%(name)s - %(asctime)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

MESSAGE_SEND = 'Успешно отправлено сообщение: {message}.'
MESSAGE_SEND_ERROR = 'Сбой при отправке сообщения: {message}.'
MESSAGE_NOT_SEND = 'Не удалось доставить пользователю сообщение об ошибке.'
API_REQUEST_ERROR = (
    'Не удалось обратиться к API Яндекс Практикума.'
    ' Использован: URL={url}, headers={headers}, params={params}'
)
STATUS_CODE_ERROR = (
    'Получен неожиданный ответ от сервера: {code}.'
    ' Использован: URL={url}, headers={headers}, params={params}'
)
RESPONSE_ERROR = (
    'API отказало в обслуживании. {key}: {value}'
)
TYPE_ERROR_RESPONSE = (
    'Полученный ответ API не является типом dict. Тип ответа: {type}'
)
KEY_ERROR = 'В словаре отстутсвует необходимый ключ: homeworks'
TYPE_ERROR_HOMEWORK = (
    'Полученные домашние работы не содержаться в list. Тип: {type}'
)
STATUS_EXCEPTION = 'Неожиданный статус домашней работы: {status}'
PARSE_STATUS = 'Изменился статус проверки работы "{name}". {verdict}'
MISSING_TOKEN = 'Токен {name} отсутствует. Программа отсановлена.'
TOKENS_LOAD_CORRECTLY = 'Токены загрузились корректно.'
TOKENS_LOAD_UNCORRECTLY = (
    'Отсутствует одна или несколько из обязательных переменных.'
)
START = 'Бот начал работу'
NO_UPDATES = 'Обновлений нет'
ERROR = 'Сбой в работе программы: {error}'

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Send message to me in Telegram."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logger.debug(MESSAGE_SEND.format(message=message))
    except TelegramError:
        logger.error(MESSAGE_SEND_ERROR.format(message=message), exc_info=True)
        raise exceptions.SendMessageError(
            MESSAGE_SEND_ERROR.format(message=message)
        )


def get_api_answer(timestamp):
    """Get answer from Yandex Practicum API."""
    params = {'from_date': timestamp}
    data = dict(url=ENDPOINT, headers=HEADERS, params=params)
    try:
        response = requests.get(**data)
    except requests.exceptions.RequestException:
        raise ConnectionError(API_REQUEST_ERROR.format(**data))
    if response.status_code != HTTPStatus.OK:
        raise exceptions.StatusCodeError(STATUS_CODE_ERROR.format(
            code=response.status_code,
            **data
        ))
    json = response.json()
    for key, value in json.items():
        if (key == "error") or (key == "code"):
            raise exceptions.ResponseError(RESPONSE_ERROR.format(
                key=key,
                value=value
            ))
    return json


def check_response(response):
    """Check response from Yandex Practicum API."""
    if not isinstance(response, dict):
        raise TypeError(TYPE_ERROR_RESPONSE.format(type=type(response)))
    if 'homeworks' not in response:
        raise exceptions.KeyError(KEY_ERROR)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(TYPE_ERROR_HOMEWORK.format(type=type(homeworks)))
    return homeworks


def parse_status(homework):
    """Parse homework from response of Yandex Practicum API."""
    if 'homework_name' not in homework:
        raise exceptions.KeyError(KEY_ERROR.format(key='homework_name'))
    name = homework['homework_name']
    if 'status' not in homework:
        raise exceptions.KeyError(KEY_ERROR.format(key='status'))
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise exceptions.HomeworkStatusError(
            STATUS_EXCEPTION.format(status=status)
        )
    verdict = HOMEWORK_VERDICTS.get(status)
    return PARSE_STATUS.format(name=name, verdict=verdict)


def check_tokens():
    """Check if tokens load correctly."""
    is_correct = True
    for name in TOKENS:
        if globals()[name] is None:
            logger.critical(MISSING_TOKEN.format(name=name))
            is_correct = False
    logger.debug(TOKENS_LOAD_CORRECTLY)
    return is_correct


def main():
    """Do main bot logic."""
    if not check_tokens():
        logger.critical(TOKENS_LOAD_UNCORRECTLY)
        raise ValueError(TOKENS_LOAD_UNCORRECTLY)

    logger.info(START)
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
                    logger.debug(NO_UPDATES)
                current_timestamp = response['current_date']
        except Exception as error:
            message = ERROR.format(error=error)
            logger.error(message, exc_info=True)
            try:
                send_message(bot=bot, message=message)
            except exceptions.SendMessageError:
                logger.error(MESSAGE_NOT_SEND)
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
