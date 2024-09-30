FROM python:3.12

# expose port 10000 for prometheus
EXPOSE 10000/udp
EXPOSE 10000/tcp

ADD requirements.txt .
RUN pip3 install -r requirements.txt

ADD bot.py .
ADD config.py .

ENTRYPOINT ["python3", "bot.py"]
