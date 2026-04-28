FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY generators/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY generators/ /app/

COPY configs/generators /app/configs/generators

ENV GENERATOR_CONFIG_DIR=/app/configs/generators \
    GENERATOR_SETTINGS_FILE=/app/configs/generators/company.generator.json

CMD ["python", "-u", "generator.py"]
