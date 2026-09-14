FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN useradd --create-home --uid 1000 bot

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot ./bot

RUN mkdir -p /app/data && chown bot:bot /app/data

USER bot

CMD ["python", "-m", "bot.main"]
