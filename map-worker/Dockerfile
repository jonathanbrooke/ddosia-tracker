FROM python:3.9-slim
WORKDIR /app
COPY map-worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY map-worker /app
ENV PYTHONUNBUFFERED=1
CMD ["python", "worker.py"]