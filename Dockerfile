FROM python:3.10.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y ffmpeg

COPY app/ ./app/
RUN mkdir -p /app/app/static
COPY app/static/ /app/app/static/
RUN mkdir -p downloads

COPY requirements.txt .
RUN apt-get install -y build-essential && \
    pip install -r requirements.txt

ENV DOWNLOADS_DIR="/app/downloads"

EXPOSE 3838

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3838"]
