import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACT_TOKEN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TG_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
FROM_DATE = 0

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
    'reviewing': 'Работа взята на проверку ревьюером.',
}

logging.basicConfig(
    format=(
        '%(asctime)s - %(levelname)s'
        '- %(message)s - %(lineno)d - %(funcName)s'
    ),
    # Из-за единого центра регистрации сообщений об ошибках, ошибки error
    # в логах всегда указывают на одну и ту же строчку и функцию,
    # из-за чего %(lineno)d не приносит особой пользы :(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w'
)


def check_tokens():
    """Проверка доступности токенов."""
    tokens = {
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID,
    }
    for token in tokens:
        if token is None:
            logging.critical(f'{token} отсутствует')
            return False
    logging.info('Токены найдены')
    return True


def send_message(bot, message):
    """Бот отправляет сообщение."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message) 
    except telegram.TelegramError as message:
        logging.error(f'Ошибка при отправке сообщения: {message}')
    else:
        logging.debug('Сообщение успешно отправлено')
# в send_message я пытался избавиться от логирования, но,
# к сожалению, тесты выдают ошибку, если я не логирую события в этой функции


def get_api_answer(timestamp):
    """Делаем запрос к API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException:
        message = f'Ошибка при запросе к API: {response.status_code}'
        raise requests.exceptions.RequestException(message)
    if response.status_code != HTTPStatus.OK:
        response.raise_for_status()
    logging.info('Ответ на запрос к API: 200 OK')
    return response.json()


def check_response(response):
    """Проверяем правильность ответа API."""
    if not isinstance(response, dict):
        raise TypeError('API возвращает не словарь.')
    if 'homeworks' not in response:
        raise KeyError('Не найден ключ homeworks.')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('API возвращает не список.')
    return response.get('homeworks')


def parse_status(homework):
    """Проверяем статус домашней работы."""
    if not isinstance(homework, dict):
        raise KeyError('API возвращает не словарь.')
    if 'status' not in homework:
        raise KeyError('В ответе нет homework_name.')
    if 'homework_name' not in homework:
        raise KeyError('В ответе нет homework_name.')
    if not isinstance(homework.get('status'), str):
        raise TypeError('status не str.')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise Exception('Неизвестный статус работы')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return (
        'Изменился статус проверки работы '
        f'"{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    logging.info('Бот запущен')
    if not check_tokens():
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = FROM_DATE
    while True:
        try:
            response_result = get_api_answer(timestamp)
            homeworks = check_response(response_result)
            logging.info("Список домашних работ получен")
            if len(homeworks) > 0:
                send_message(bot, parse_status(homeworks[0]))
                timestamp = response_result['current_date']
            else:
                logging.info("Новые задания не обнаружены")
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
