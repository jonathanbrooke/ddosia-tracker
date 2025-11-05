FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY gdelt-query-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY gdelt-query-service/app.py .
COPY gdelt-query-service/static ./static

# Expose port
EXPOSE 8001

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8001", "--workers", "2", "--timeout", "60", "app:app"]
