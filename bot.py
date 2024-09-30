import telebot
import psycopg2
import re
from prometheus_client import start_http_server, Summary, Counter
from telebot.types import Chat, Message, User, CallbackQuery, InlineQuery
import logging

import config


opt_in = Summary('opt_in_latency_seconds', 'Opt in latency')
opt_out = Summary('opt_out_latency_seconds', 'Opt out latency')
ping = Summary('ping_latency_seconds', 'Ping latency')
lists = Summary('list_latency_seconds', 'List latency')
inline = Summary('inline_latency_seconds', 'Inline latency')
reply = Summary('reply_latency_seconds', 'Reply latency')

exceptions = Counter('exception_counts', 'Exceptions count')


logger = telebot.logger
logger.setLevel(logging.WARNING)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')


bot = telebot.TeleBot(config.TELEGRAM_KEY)


@bot.message_handler(commands=['create'])
def create(message: Message):
    chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if not (chat_member.status in ['creator', 'administrator'] or message.chat.type == 'private'):
        bot.reply_to(message, "You don't have permissions. Only admins can create and remove aliases")
        return

    args = message.text.split(' ')
    if len(args) != 2 or not args[1].isprintable() or len(args[1].lstrip('@')) == 0:
        bot.reply_to(message, "You need to use create with an alias name. See /help for more information")
        return
    try:
        alias = args[1].lstrip('@')

        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute('insert into chat (id) values (%s) on conflict do nothing', (message.chat.id,))
        c.execute('insert into ping (chat_id, alias) values (%s, %s)',
                  (message.chat.id, alias))
        conn.commit()
        conn.close()

        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👍")])
        bot.reply_to(message, rf"You created `@{alias}`\. Now you can `/opt_in {alias}`", parse_mode='MarkdownV2')
    except Exception as ex:
        exceptions.inc()
        logger.exception(ex)
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


@bot.message_handler(commands=['remove'])
def remove(message: Message):
    chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if not (chat_member.status in ['creator', 'administrator'] or message.chat.type == 'private'):
        bot.reply_to(message, "You don't have permissions. Only admins can create and remove aliases")
        return

    args = message.text.split(' ')
    if len(args) not in [2, 3] or not args[1].isprintable() or len(args[1].lstrip('@')) == 0:
        bot.reply_to(message, "You need to use remove with an alias name. See /help for more information")
        return
    try:
        alias = args[1].lstrip('@')

        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute('select count(user_id) from ping_user '
                  'left join ping on ping_user.ping_id = ping.id '
                  'where chat_id = %s and alias = %s',
                  (message.chat.id, alias))
        cnt = c.fetchone()[0]

        if cnt == 0 or (len(args) == 3 and args[2] == '--force'):
            c.execute('delete from ping_user where ping_id = '
                      '(select id from ping where chat_id = %s and alias = %s)',
                      (message.chat.id, alias))
            c.execute('delete from ping where chat_id=%s and alias=%s',
                      (message.chat.id, alias))
            conn.commit()
            bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👍")])
        else:
            bot.reply_to(message, rf'Alias `{alias}` is not empty\. To get all users inside run `/list`\.'
                                  f'\nIf you are sure you want to delete it run `/remove {alias} --force`',
                         parse_mode='MarkdownV2')
        conn.close()
    except Exception as ex:
        exceptions.inc()
        logger.exception(ex)
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


@bot.message_handler(commands=['help'])
def help_(message: Message):
    bot.reply_to(message, rf"""
/help \- this message
/create \- create new alias for pings
/remove \- remove alias
/opt\_in name \- add yourself (or user, on which you reply with the command) to the alias with name
/opt\_out name \- remove yourself (or user, on which you reply with the command) from the name
/get\_out \- remove yourself from all the pings in this chat
/list \- get list of aliases with people

Also, there is inline mode: use `@{bot.get_me().username} ping` and `@{bot.get_me().username} opt_out`""",
                 parse_mode='MarkdownV2')


@bot.message_handler(commands=['opt_in', 'opt-in'])
@opt_in.time()
def opt_in(message: Message):
    args = message.text.split(' ')
    if len(args) != 2:
        bot.reply_to(message, "You need to use opt-in with an alias name. See /help for more information")
        return
    try:
        if message.reply_to_message is not None and not message.reply_to_message.from_user.is_bot:
            user_id = message.reply_to_message.from_user.id
        else:
            user_id = message.from_user.id

        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute('insert into "user" (id) values (%s) on conflict do nothing', (user_id,))
        c.execute('insert into ping_user (ping_id, user_id) '
                  '(select id, %s from ping where chat_id = %s and alias = %s)',
                  (user_id, message.chat.id, args[1]))
        conn.commit()
        conn.close()
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👍")])
    except Exception as ex:
        exceptions.inc()
        logger.exception(ex)
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


@bot.message_handler(commands=['opt_out', 'opt-out'])
@opt_out.time()
def opt_out(message: Message):
    args = message.text.split(' ')
    if len(args) != 2:
        bot.reply_to(message, "You need to use opt-out with an alias name. See /help for more information")
        return
    try:
        if message.reply_to_message is not None and not message.reply_to_message.from_user.is_bot:
            user_id = message.reply_to_message.from_user.id
        else:
            user_id = message.from_user.id

        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute('delete from ping_user where user_id = %s and ping_id = '
                  '(select id from ping where chat_id = %s and alias = %s)',
                  (user_id, message.chat.id, args[1]))
        conn.commit()
        conn.close()
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👍")])
    except Exception as ex:
        exceptions.inc()
        logger.exception(ex)
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


@bot.message_handler(commands=['list'])
@lists.time()
def list_(message: Message):
    try:
        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute('select alias, user_id from ping '
                  'left join ping_user on ping.id = ping_user.ping_id '
                  'where chat_id = %s', (message.chat.id,))

        if c.rowcount == 0:
            bot.reply_to(message, 'There are no aliases yet')
            return

        result = dict()
        for alias, user_id in c:
            if user_id is None:
                if alias not in result:
                    result[alias] = []
            else:
                if alias in result:
                    result[alias] += [user_id]
                else:
                    result[alias] = [user_id]

        conn.close()

        ret = ''
        for alias, users in result.items():
            ret += f'• {alias}: '  # &#8226;
            for user_id in users:
                ret += f'{bot.get_chat_member(message.chat.id, user_id).user.username} '

            ret += '\n'

        bot.reply_to(message, ret)
    except Exception as ex:
        exceptions.inc()
        logger.exception(ex)
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


@bot.message_handler(commands=['get-out', 'get_out'])
def get_out(message: Message):
    try:
        remove_from_all(message.from_user, message.chat)
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👍")])
    except Exception:
        exceptions.inc()
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


def remove_from_all(user: User, chat: Chat):
    conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
    c = conn.cursor()
    c.execute('delete from ping_user where user_id = %s and ping_id in '
              '(select id from ping where chat_id = %s)',
              (user.id, chat.id))
    conn.commit()
    conn.close()


@bot.message_handler(content_types=['left_chat_member'])
def user_left(message: Message):
    try:
        remove_from_all(message.left_chat_member, message.chat)
    except Exception as ex:
        exceptions.inc()
        logger.exception(ex)
        bot.reply_to(message, 'Unable to auto delete user from pings.\n'
                              'You will run into problems later =(\n'
                              'You can try to manually delete by opt-outing left user from every ping')


@bot.message_handler(regexp=r'(.*[@/]\S+.*)')
@ping.time()
def ping(message: Message):
    try:
        aliases = re.findall(r'.*?[@/](\w+).*?', message.text)
        user_ids = set()

        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()

        c.execute('select distinct user_id from ping '
                  'left join ping_user on ping.id = ping_user.ping_id '
                  'where chat_id = %s and alias in %s', (message.chat.id, tuple(aliases)))

        if c.rowcount == 0:
            conn.close()
            return

        for user_id in c:
            if user_id[0] is not None:
                user_ids.add(user_id[0])

        conn.close()

        if message.from_user.id in user_ids:
            user_ids.remove(message.from_user.id)

        write = list()
        cnt = 0
        ind = 0

        for user_id in user_ids:
            if cnt == 0:
                write += ['']
            write[ind] += f'@{bot.get_chat_member(message.chat.id, user_id).user.username}, '
            cnt += 1
            if cnt >= config.MAX_PINGS_PER_MESSAGE - 1:
                cnt = 0
                ind += 1

        try:
            bot.delete_message(message.chat.id, message.id)
        except Exception:
            exceptions.inc()

        if len(user_ids) == 0:
            bot.send_message(message.chat.id, f'@{message.from_user.username} said "{message.text}".\n'
                                              f'Noone will be pinged from your request, because {aliases} are empty. '
                                              f'You can /list them')
            return

        bot.send_message(message.chat.id,
                         f'@{message.from_user.username} said "{message.text}".\n'
                         f'And pinged: {write[0][:-2]}{"..." if len(write) > 1 else ""}',
                         reply_markup=config.KEYBOARD_MARKUP)

        ind = 0
        for msg in write[1:]:
            if msg == '':
                continue
            ind += 1
            bot.send_message(message.chat.id,
                             f'...{msg[:-2]}{"..." if len(write) > ind + 1 else "."}')
    except Exception as ex:
        exceptions.inc()
        logger.exception(ex)
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


@bot.callback_query_handler(func=lambda callback: True)
def handle_query(callback: CallbackQuery):
    try:
        previous_text = callback.message.text

        text = re.sub(rf'((^|\n)[{"".join(config.KEYBOARD_MARKUP_CHARS)}]:.*?)(?: {callback.from_user.username})(.*?($|\n))',
                      r'\g<1>\g<3>',
                      previous_text)

        text = re.sub(rf'(?:^|\n)[{"".join(config.KEYBOARD_MARKUP_CHARS)}]:($|\n)',
                      r'\g<1>',
                      text)

        text, changes = re.subn(rf'((^|\n){callback.data}:.*?)($|\n)',
                                rf'\g<1> {callback.from_user.username}\g<3>',
                                text)

        if changes == 0:
            text += f'\n{callback.data}: {callback.from_user.username}'

        bot.edit_message_text(text, callback.message.chat.id, callback.message.id, reply_markup=config.KEYBOARD_MARKUP)
    except Exception as ex:
        exceptions.inc()
        logger.exception(ex)


@bot.message_handler(regexp='(^(?![/]).*)')
@reply.time()
def check_reply(message: Message):
    try:
        if message.reply_to_message is not None and message.reply_to_message.from_user.id == bot.get_me().id and \
                message.reply_to_message.text.split(' ')[0].startswith('@'):
            try:
                bot.delete_message(message.chat.id, message.id)
            except Exception:
                exceptions.inc()

            bot.reply_to(message.reply_to_message,
                         f'@{message.from_user.username} said "{message.text[:config.MESSAGE_LENGTH]}".\n'
                         f'For: {message.reply_to_message.text.split(" ")[0]}')
    except Exception as ex:
        exceptions.inc()
        logger.exception(ex)


@bot.inline_handler(lambda query: query.query == 'ping')
def ping_query(inline_query: InlineQuery):
    inline_mode(inline_query, "/")


@bot.inline_handler(lambda query: query.query in ['opt_out', 'opt-out'])
def opt_out_query(inline_query: InlineQuery):
    inline_mode(inline_query, "/opt_out ")


@inline.time()
def inline_mode(inline_query: InlineQuery, message: str):
    try:
        aliases = list()
        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute('select alias, chat_id from ping '
                  'join ping_user on ping.id = ping_user.ping_id '
                  'where user_id = %s order by alias', (inline_query.from_user.id,))

        ind = 1
        for alias, chat_id in c:
            chat = bot.get_chat(chat_id)
            aliases.append(
                telebot.types.
                InlineQueryResultArticle(f'{ind}',
                                         f'{"@" + bot.get_me().username if chat.type == "private" else chat.title}: {alias}',
                                         telebot.types.InputTextMessageContent(f'{message}{alias}')))
            ind += 1

        conn.close()
        bot.answer_inline_query(inline_query.id, aliases, is_personal=True, cache_time=config.INLINE_CACHE_TIME)
    except Exception as ex:
        exceptions.inc()
        logger.exception(ex)


if __name__ == "__main__":
    start_http_server(port=10000)
    bot.infinity_polling()
