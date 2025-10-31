FROM python:3.9-slim

WORKDIR /app
COPY map-service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY map-service /app

# Copy geopolitical events data
COPY map-worker/mappings /app/mappings

ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:8000 app:app --workers ${GUNICORN_WORKERS:-2}"]
