import telebot
import datetime
import time
import psycopg2
import re
from prometheus_client import start_http_server, Summary, Counter

import config

bot = telebot.TeleBot(config.TELEGRAM_KEY)

opt_in = Summary('opt_in_latency_seconds', 'Opt in latency')
opt_out = Summary('opt_out_latency_seconds', 'Opt out latency')
ping = Summary('ping_latency_seconds', 'Ping latency')
lists = Summary('list_latency_seconds', 'List latency')
inline = Summary('inline_latency_seconds', 'Inline latency')
reply = Summary('reply_latency_seconds', 'Reply latency')

exceptions = Counter('exception_counts', 'Exceptions count')
exceptions_global = Counter('exception_global_counts', 'Global exceptions count')


@bot.message_handler(commands=['create'])
def create(message):
    chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if not (chat_member.status in ['creator', 'administrator'] or message.chat.type == 'private'):
        bot.reply_to(message, "You don't have permissions. Only admins can create and remove aliases")
        return

    args = message.text.split(' ')
    if len(args) != 2:
        bot.reply_to(message, "You need to use create with an alias name. See /help for more information")
        return
    try:
        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute('insert into chat (id) values (%s) on conflict do nothing', (message.chat.id,))
        c.execute('insert into ping (chat_id, alias) values (%s, %s)',
                  (message.chat.id, args[1]))
        conn.commit()
        conn.close()

        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👍")])
        bot.reply_to(message, rf"You created `@{args[1]}`\. Now you can `/opt_in {args[1]}`", parse_mode='MarkdownV2')
    except Exception:
        exceptions.inc()
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


@bot.message_handler(commands=['remove'])
def remove(message):
    chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
    if not (chat_member.status in ['creator', 'administrator'] or message.chat.type == 'private'):
        bot.reply_to(message, "You don't have permissions. Only admins can create and remove aliases")
        return

    args = message.text.split(' ')
    if len(args) not in [2, 3]:
        bot.reply_to(message, "You need to use remove with an alias name. See /help for more information")
        return
    try:
        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute('select count(user_id) from ping_user '
                  'left join ping on ping_user.ping_id = ping.id '
                  'where chat_id = %s and alias = %s',
                  (message.chat.id, args[1]))
        cnt = c.fetchone()[0]

        if cnt == 0 or (len(args) == 3 and args[2] == '--force'):
            c.execute('delete from ping_user where ping_id = '
                      '(select id from ping where chat_id = %s and alias = %s)',
                      (message.chat.id, args[1]))
            c.execute('delete from ping where chat_id=%s and alias=%s',
                      (message.chat.id, args[1]))
            conn.commit()
            bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👍")])
        else:
            bot.reply_to(message, rf'Alias `{args[1]}` is not empty\. To get all users inside run `/list`\.\n'
                                  f'If you are sure you want to delete it run `/remove {args[1]} --force`',
                         parse_mode='MarkdownV2')
        conn.close()
    except Exception:
        exceptions.inc()
        print(exception)
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


@bot.message_handler(commands=['help'])
def help_(message):
    bot.reply_to(message, rf"""
/help \- this message
/create \- create new alias for pings
/remove \- remove alias
/opt\_in name \- add yourself to the alias with name
/opt\_out name \- remove yourself from the name
/list \- get list of aliases with people

Also, there is inline mode: use `@{bot.get_me().username} ping` and `@{bot.get_me().username} opt_out`""",
                 parse_mode='MarkdownV2')


@bot.message_handler(commands=['opt_in', 'opt-in'])
@opt_in.time()
def opt_in(message):
    args = message.text.split(' ')
    if len(args) != 2:
        bot.reply_to(message, "You need to use opt-in with an alias name. See /help for more information")
        return
    try:
        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute('insert into "user" (id) values (%s) on conflict do nothing', (message.from_user.id,))
        c.execute('insert into ping_user (ping_id, user_id) '
                  '(select id, %s from ping where chat_id = %s and alias = %s)',
                  (message.from_user.id, message.chat.id, args[1]))
        conn.commit()
        conn.close()
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👍")])
    except Exception:
        exceptions.inc()
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


@bot.message_handler(commands=['opt_out', 'opt-out'])
@opt_out.time()
def opt_out(message):
    args = message.text.split(' ')
    if len(args) != 2:
        bot.reply_to(message, "You need to use opt-out with an alias name. See /help for more information")
        return
    try:
        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute('delete from ping_user where user_id = %s and ping_id = '
                  '(select id from ping where chat_id = %s and alias = %s)',
                  (message.from_user.id, message.chat.id, args[1]))
        conn.commit()
        conn.close()
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👍")])
    except Exception:
        exceptions.inc()
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


@bot.message_handler(commands=['list'])
@lists.time()
def list_(message):
    try:
        conn = psycopg2.connect(config.DATABASE_URL, sslmode='require')
        c = conn.cursor()
        c.execute('select alias, user_id from ping '
                  'left join ping_user on ping.id = ping_user.ping_id '
                  'where chat_id = %s', (message.chat.id,))

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
            ret += f'{alias}: '
            for user_id in users:
                ret += f'{bot.get_chat_member(message.chat.id, user_id).user.username} '

            ret += '\n'

        bot.reply_to(message, ret)
    except Exception:
        exceptions.inc()
        bot.set_message_reaction(message.chat.id, message.id, [telebot.types.ReactionTypeEmoji("👎")])


@bot.message_handler(regexp=r'(.*[@/]\S+.*)')
@ping.time()
def ping(message):
    try:
        aliases = re.findall(r'.*?[@/](\S+).*?', message.text)
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

        write = ['']
        cnt = 0
        ind = 0

        for user_id in user_ids:
            write[ind] += f'@{bot.get_chat_member(message.chat.id, user_id).user.username}, '
            cnt += 1
            if cnt == 4:
                cnt = 0
                ind += 1
                write += ['']

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
                         f'And pinged: {write[0][:-2]}{"..." if len(write) > 1 else ""}')
        ind = 0
        for msg in write[1:]:
            if msg == '':
                continue
            ind += 1
            bot.send_message(message.chat.id,
                             f'...{msg[:-2]}{"..." if len(write) > ind + 1 else "."}')
    except Exception:
        exceptions.inc()
        bot.reply_to(message, "Something went wrong")


@bot.message_handler(regexp='(^(?![/]).*)')
@reply.time()
def check_reply(message):
    try:
        if message.reply_to_message is not None and message.reply_to_message.from_user.id == bot.get_me().id and \
                message.reply_to_message.text.split(' ')[0].startswith('@'):
            try:
                bot.delete_message(message.chat.id, message.id)
            except Exception:
                exceptions.inc()

            bot.reply_to(message.reply_to_message,
                         f'@{message.from_user.username} said "{message.text[:config.MESSAGE_LENGTH]}".\n'
                         f'Для: {message.reply_to_message.text.split(" ")[0]}')
    except Exception:
        exceptions.inc()


@bot.inline_handler(lambda query: query.query == 'ping')
def ping_query(inline_query):
    inline_mode(inline_query, "/")


@bot.inline_handler(lambda query: query.query in ['opt_out', 'opt-out'])
def opt_out_query(inline_query):
    inline_mode(inline_query, "/opt_out ")


@inline.time()
def inline_mode(inline_query, message):
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
    except Exception as e:
        exceptions.inc()
        print(e)


if __name__ == "__main__":
    try:
        start_http_server(port=10000)
        print(f'I am @{bot.get_me().username} and I started at '
              f'{datetime.datetime.isoformat(datetime.datetime.now())}')
        bot.polling()
    except InterruptedError:
        exit(0)
    except Exception as exception:
        exceptions_global.inc()
        print(exception)
        time.sleep(10)
