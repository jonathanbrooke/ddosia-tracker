FROM python:3.9-slim
WORKDIR /app
COPY gdelt-worker/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY gdelt-worker /app
RUN chmod +x /app/run_loop.sh
ENV PYTHONUNBUFFERED=1
CMD ["bash", "run_loop.sh"]
