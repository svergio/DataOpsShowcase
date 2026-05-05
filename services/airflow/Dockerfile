ARG AIRFLOW_IMAGE_TAG=2.9.3-python3.11
FROM apache/airflow:${AIRFLOW_IMAGE_TAG}

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       openjdk-17-jre-headless \
       procps \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sfn "/usr/lib/jvm/java-17-openjdk-$(dpkg --print-architecture)" /usr/local/airflow-java

ENV JAVA_HOME=/usr/local/airflow-java

USER airflow
COPY services/airflow/requirements.txt /tmp/requirements.txt
RUN PYTHON_VERSION="$(python -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))")" \
    && CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt" \
    && pip install --no-cache-dir --default-timeout=180 \
       "apache-airflow==${AIRFLOW_VERSION}" \
       -r /tmp/requirements.txt \
       --constraint "${CONSTRAINT_URL}"
