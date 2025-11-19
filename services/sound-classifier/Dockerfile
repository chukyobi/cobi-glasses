FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (curl is required for downloading models)
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# COPY 1: Copy Requirements file
COPY services/sound-classifier/requirements.txt .
# Install Python dependencies
RUN pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org && \
    pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    --default-timeout=1000 --no-cache-dir -r requirements.txt

# COPY 2: Copy the Shared Config folder (from root context)
COPY shared /app/shared

# COPY 3: Copy the application code files (app.py and entrypoint.sh)
COPY services/sound-classifier/app.py .
COPY services/sound-classifier/entrypoint.sh .

# Ensure Python finds shared module
ENV PYTHONPATH=/app

# Use a custom entrypoint script to attempt download at runtime
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]