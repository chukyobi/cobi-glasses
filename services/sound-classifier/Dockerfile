FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for webrtcvad and build tools
# Adding 'build-essential' to provide 'gcc' and 'make'
RUN apt-get update && apt-get install -y \
    libasound2-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]