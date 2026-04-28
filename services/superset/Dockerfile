ARG SUPERSET_IMAGE_TAG=latest
FROM apache/superset:${SUPERSET_IMAGE_TAG}

USER root
RUN uv pip install --python /app/.venv/bin/python psycopg2-binary==2.9.9

USER superset
