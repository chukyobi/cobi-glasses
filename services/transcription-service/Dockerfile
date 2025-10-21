FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for faster-whisper (ffmpeg + lib dependencies)
RUN apt-get update \
    && apt-get install -y \
        ffmpeg \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        # Add the required build tools and FFmpeg development headers
        pkg-config \
        libavformat-dev \
        libavcodec-dev \
        libavdevice-dev \
        libavutil-dev \
        libswresample-dev \
        libswscale-dev \
        # Cleanup
    && rm -rf /var/lib/apt/lists/*
# Install Python dependencies
COPY requirements.txt .
# Increase timeout to 600 seconds (10 minutes)
RUN pip install --no-cache-dir -r requirements.txt --timeout 600

# Copy application code
COPY . .

# Run the transcription service
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002"]