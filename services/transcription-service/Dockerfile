FROM python:3.10-slim
WORKDIR /app
# Install ffmpeg for Whisper
RUN apt-get update && apt-get install -y ffmpeg build-essential && rm -rf /var/lib/apt/lists/*
COPY services/transcription-service/requirements.txt .
# Upgrade pip first, then install requirements with a massive timeout
# UPDATE THIS SECTION: Add trusted-host flags to bypass SSL strictness
RUN pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org && \
    pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    --default-timeout=1000 --no-cache-dir -r requirements.txt
COPY shared /app/shared
COPY services/transcription-service .
ENV PYTHONPATH=/app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]