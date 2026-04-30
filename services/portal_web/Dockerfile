FROM python:3.11-slim

WORKDIR /app

COPY services/portal_web/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY services/portal_web /app

ENV PYTHONUNBUFFERED=1
EXPOSE 8050

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:8050", "--timeout", "60", "app:app"]
