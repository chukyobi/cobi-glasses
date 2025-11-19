#!/bin/bash
set -e

MODEL_PATH="/app/yamnet.tflite"
CLASS_MAP_PATH="/app/yamnet_class_map.csv"

echo "Running Model Validation and Download Check..."

# Check if files already exist and are valid
if [ -f "$MODEL_PATH" ] && [ -s "$MODEL_PATH" ] && [ -f "$CLASS_MAP_PATH" ] && [ -s "$CLASS_MAP_PATH" ]; then
    MODEL_SIZE=$(wc -c < "$MODEL_PATH" 2>/dev/null || echo 0)
    if [ "$MODEL_SIZE" -gt 1000000 ]; then
        echo "Model files already exist and are valid. Starting service..."
        exec uvicorn app:app --host 0.0.0.0 --port 8001
    fi
fi

echo "Downloading model files..."

# Download using Python script
python3 << 'PYTHON_SCRIPT'
import urllib.request
import ssl
import sys

# Correct URLs for YAMNet
CLASS_MAP_URL = "https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv"
MODEL_URL = "https://tfhub.dev/google/lite-model/yamnet/tflite/1?lite-format=tflite"

CLASS_MAP_PATH = "/app/yamnet_class_map.csv"
MODEL_PATH = "/app/yamnet.tflite"

print("Downloading class map...")
try:
    urllib.request.urlretrieve(CLASS_MAP_URL, CLASS_MAP_PATH)
    print("Class map downloaded successfully")
except Exception as e:
    print(f"Failed to download class map: {e}")
    sys.exit(1)

print("Downloading YAMNet model...")
try:
    # TensorFlow Hub requires following redirects
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
    urllib.request.install_opener(opener)
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    print("YAMNet model downloaded successfully")
except Exception as e:
    print(f"Failed to download model: {e}")
    sys.exit(1)

# Validate
import os
model_size = os.path.getsize(MODEL_PATH)
if model_size > 1000000:
    print(f"Model validated: {model_size} bytes")
else:
    print(f"Model file too small: {model_size} bytes")
    sys.exit(1)
PYTHON_SCRIPT

if [ $? -eq 0 ]; then
    echo "Starting service..."
    exec uvicorn app:app --host 0.0.0.0 --port 8001
else
    echo "CRITICAL FAILURE: Could not download model files."
    exit 1
fi