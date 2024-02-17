FROM python:3.11
# TODO migrate to 3.12

ENV DATABASE_URL=${DATABASE_URL}
ENV TELEGRAM_KEY=${TELEGRAM_KEY}

ADD requirements.txt .
RUN pip3 install -r requirements.txt

ADD bot.py .
ADD config.py .

CMD python3 bot.py
