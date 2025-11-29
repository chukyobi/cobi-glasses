# # Use Python 3.11 slim image for smaller size
# FROM python:3.11-slim

# # Set working directory
# WORKDIR /app

# # Install system dependencies (only if av installation fails without them)
# # Uncomment if needed:
# # RUN apt-get update && apt-get install -y \
# #     ffmpeg \
# #     libavcodec-dev \
# #     libavformat-dev \
# #     libavutil-dev \
# #     && rm -rf /var/lib/apt/lists/*

# # Copy requirements first for better caching
# COPY requirements.txt .

# # Install Python dependencies
# RUN pip install --no-cache-dir -r requirements.txt

# # Download faster-whisper model at build time (optional but recommended)
# # This makes startup faster and works offline
# RUN python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8')"

# # Copy application code
# COPY . .

# # Create non-root user for security
# RUN useradd -m -u 1000 transcriber && chown -R transcriber:transcriber /app
# USER transcriber

# # Expose port
# EXPOSE 8002

# # Health check
# HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
#     CMD python -c "import requests; requests.get('http://localhost:8002/health')" || exit 1

# # Run the application
# CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]


# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for downloading models
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements-vosk.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Download Vosk model at build time (recommended)
# This makes the container fully self-contained and offline-ready
RUN mkdir -p models && \
    cd models && \
    wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip && \
    unzip vosk-model-small-en-us-0.15.zip && \
    rm vosk-model-small-en-us-0.15.zip && \
    cd ..

# Copy application code
COPY app.py .

# Create non-root user for security
RUN useradd -m -u 1000 transcriber && \
    chown -R transcriber:transcriber /app
USER transcriber

# Set environment variables
ENV VOSK_MODEL_PATH=/app/models/vosk-model-small-en-us-0.15
ENV INPUT_SAMPLE_RATE=16000

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8002/health').raise_for_status()" || exit 1

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8002", "--log-level", "info"]