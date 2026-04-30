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

COPY services/postgres/init/02b_oltp_marketing_hr_finance.sql /app/sql/02b_oltp_marketing_hr_finance.sql

COPY services/postgres/init/02c_oltp_retail_legacy.sql /app/sql/02c_oltp_retail_legacy.sql

COPY configs/generators /app/configs/generators

ENV GENERATOR_CONFIG_DIR=/app/configs/generators \
    GENERATOR_SETTINGS_FILE=/app/configs/generators/company.generator.json \
    OLTP_EXTENSIONS_SQL=/app/sql/02b_oltp_marketing_hr_finance.sql

CMD ["python", "-u", "generator.py"]
