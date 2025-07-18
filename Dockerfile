FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .

RUN pip install -r requirements.txt
RUN apt-get update && apt-get install -y ffmpeg

CMD ["python", "discordBot.py"]
