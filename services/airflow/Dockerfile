ARG AIRFLOW_IMAGE_TAG=2.9.3-python3.11
FROM apache/airflow:${AIRFLOW_IMAGE_TAG}

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

USER airflow
COPY services/airflow/requirements.txt /tmp/requirements.txt
RUN PYTHON_VERSION="$(python -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))")" \
    && CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt" \
    && pip install --no-cache-dir --default-timeout=180 \
       "apache-airflow==${AIRFLOW_VERSION}" \
       -r /tmp/requirements.txt \
       --constraint "${CONSTRAINT_URL}"
