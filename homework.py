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
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    filename='main.log',
    filemode='w')


def check_tokens():
    """Проверка доступности токенов."""
    tokens = {
            PRACTICUM_TOKEN,
            TELEGRAM_TOKEN,
            TELEGRAM_CHAT_ID
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
    except Exception:
        logging.error('Ошибка при отправке сообщения')
    else:
        logging.debug('Сообщение успешно отправлено')
    pass


def get_api_answer(timestamp):
    """Делаем запрос к API."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            response.raise_for_status()
            logging.error('API недоступен')
        logging.info('Ответ на запрос к API: 200 OK')
        return response.json()
    except requests.exceptions.RequestException:
        message = f'Ошибка при запросе к API: {response.status_code}'
        logging.error(message)
        raise requests.exceptions.RequestException(message)


def check_response(response):
    """Проверяем правильность ответа API."""
    if isinstance(response, dict):
        if 'homeworks' in response:
            if isinstance(response.get('homeworks'), list):
                return response.get('homeworks')
            logging.error('API возвращает не список.')
            raise TypeError('API возвращает не список.')
        logging.error('Не найден ключ homeworks.')
        raise KeyError('Не найден ключ homeworks.')
    logging.error('API возвращает не словарь.')
    raise TypeError('API возвращает не словарь.')


def parse_status(homework):
    """Проверяем статус домашней работы."""
    if isinstance(homework, dict):
        if 'status' in homework:
            if 'homework_name' in homework:
                if isinstance(homework.get('status'), str):
                    homework_name = homework.get('homework_name')
                    homework_status = homework.get('status')
                    if homework_status in HOMEWORK_VERDICTS:
                        verdict = HOMEWORK_VERDICTS.get(homework_status)
                        return (
                            'Изменился статус проверки работы '
                            f'"{homework_name}". {verdict}'
                        )
                    else:
                        logging.error('Неизвестный статус работы')
                        raise Exception('Неизвестный статус работы')
                logging.error('status не str.')
                raise TypeError('status не str.')
            logging.error('В ответе нет homework_name.')
            raise KeyError('В ответе нет homework_name.')
        logging.error('В ответе нет status.')
        raise KeyError('В ответе нет status.')
    logging.error('API возвращает не словарь.')
    raise KeyError('API возвращает не словарь.')


def main():
    """Основная логика работы бота."""
    logging.info('Бот запущен')
    if check_tokens():
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
                time.sleep(RETRY_PERIOD)
            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                send_message(bot, message)
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
