FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY services/local_voice/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/local_voice /app/local_voice
ENV HF_HOME=/models
CMD ["uvicorn", "local_voice.gateway:app", "--host", "127.0.0.1", "--port", "8090", "--no-access-log"]
