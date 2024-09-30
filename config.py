import os
from telebot.util import quick_markup

MESSAGE_LENGTH = 4096

DATABASE_URL = os.environ['DATABASE_URL']
TELEGRAM_KEY = os.environ['TELEGRAM_KEY']

INLINE_CACHE_TIME = 1  # TODO increase cache_time

KEYBOARD_MARKUP_CHARS = ['✅', '🤷', '❌']
KEYBOARD_MARKUP = quick_markup({
    KEYBOARD_MARKUP_CHARS[0]: {'callback_data': KEYBOARD_MARKUP_CHARS[0]},
    KEYBOARD_MARKUP_CHARS[1]: {'callback_data': KEYBOARD_MARKUP_CHARS[1]},
    KEYBOARD_MARKUP_CHARS[2]: {'callback_data': KEYBOARD_MARKUP_CHARS[2]}
}, row_width=3)

MAX_PINGS_PER_MESSAGE = 5  # it seems that Telegram ignores mass-ping messages
