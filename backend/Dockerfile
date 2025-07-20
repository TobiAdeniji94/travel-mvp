# syntax=docker/dockerfile:1.4

FROM python:3.13-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    python -m spacy download en_core_web_lg

COPY start.sh .
RUN chmod +x start.sh

COPY . .

ENTRYPOINT ["./start.sh"]