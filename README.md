# @P1ngChatBot

Bot to allow pinging all users in group (`@all`) (and custom aliases) in Telegram. Hosted bot: [@P1ngChatBot](https://t.me/P1ngChatBot)

## Instructions

### Running

You can either use bare python or docker.
Also, there is [prometheus](https://prometheus.io/) for metrics.

First of all you need Telegram API key and PostgreSQL database (schema defined in [database.sql](database.sql))

#### Python

1. Clone `git clone https://github.com/dzen03/P1ngChatBot.git && cd p1ngchatbot`
2. _(Optional)_ Create venv `python3 -m venv venv && source venv/bin/activate`
3. Dependencies `pip3 install -r requirements.txt`
4. Fill [config.py](config.py) with API key and database link
5. Run `python3 bot.py`

#### Docker

1. Clone `git clone https://github.com/dzen03/P1ngChatBot.git && cd p1ngchatbot`
2. Build `docker build -t p1ngchatbot .`
3. Run `docker run --env DATABASE_URL=postgresql://<your database url> --env TELEGRAM_KEY=<your API key> --name p1ngchatbot p1ngchatbot`

### Using bot

1. Add to your desired group
2. Give admin privileges
3. Use `/create <alias>` to create alias _(for example `/create all`)_
4. Next `/opt_in <alias>` to add yourself to that alias (and everyone should do it too). _(e.g. `/opt_in all`)_
5. When you want to ping all users from any alias use `@<alias>` or `/alias` _(e.g. `@all`)_

If you want more info use `/help`
