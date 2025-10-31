FROM python:3.9-slim

WORKDIR /app
COPY src/ /app/src/
COPY requirements-processor.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

USER root
ENV PYTHONUNBUFFERED=1
CMD ["python", "src/processor.py"]