FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for faster-whisper (ffmpeg + lib dependencies)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the transcription service
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]