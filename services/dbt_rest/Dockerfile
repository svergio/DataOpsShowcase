FROM python:3.11-slim
ARG DBT_VERSION=1.8.2
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    "dbt-core==${DBT_VERSION}" \
    "dbt-postgres==${DBT_VERSION}"
COPY app ./app
ENV DBT_PROJECT_DIR=/workspace/dbt
ENV DBT_PROFILES_DIR=/workspace/dbt
EXPOSE 8580
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8580"]
