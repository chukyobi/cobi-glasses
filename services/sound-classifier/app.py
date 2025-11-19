import logging
import numpy as np
import uvicorn
import json
import os
import csv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import tensorflow.lite as tflite

# Import shared config
from shared.config.audio_config import SAMPLE_RATE

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [CLASSIFIER] %(message)s")
logger = logging.getLogger("SoundClassifier")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# --- YAMNet Model Setup ---
MODEL_PATH = "yamnet.tflite"
CLASS_MAP_PATH = "yamnet_class_map.csv"

# 1. Load Class Names
class_names = []
try:
    with open(CLASS_MAP_PATH, 'r') as csvfile:
        reader = csv.reader(csvfile)
        next(reader) # Skip header
        for row in reader:
            class_names.append(row[2])
    logger.info(f"Loaded {len(class_names)} audio classes.")
except Exception as e:
    logger.error(f"CRITICAL: Error loading class map: {e}")
    class_names = ["Unknown"] * 521

# 2. Load TFLite Interpreter (Global Scope)
interpreter = None
input_index = None
output_index = None

try:
    logger.info("Loading TFLite Model...")
    interpreter = tflite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    input_index = input_details[0]['index']
    output_index = output_details[0]['index']
    logger.info(f"TFLite Model Loaded Successfully.")
    logger.info(f"Input shape: {input_details[0]['shape']}, dtype: {input_details[0]['dtype']}")
    logger.info(f"Output shape: {output_details[0]['shape']}, dtype: {output_details[0]['dtype']}")
except Exception as e:
    logger.error(f"CRITICAL: Failed to load TFLite model: {e}")

# YAMNet expects exactly 15600 samples (0.975 seconds) at 16kHz
YAMNET_INPUT_SIZE = 15600 

@app.websocket("/classify")
async def classify_socket(ws: WebSocket):
    await ws.accept()
    logger.info("Client connected for Environmental Classification")
    
    # If model failed to load, close connection immediately
    if interpreter is None:
        logger.error("Cannot classify: Interpreter not loaded.")
        await ws.close(code=1011)
        return

    buffer = np.zeros(0, dtype=np.float32)
    
    try:
        while True:
            data_bytes = await ws.receive_bytes()
            
            # Convert Int16 -> Float32
            audio_chunk = np.frombuffer(data_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            buffer = np.concatenate((buffer, audio_chunk))
            
            while len(buffer) >= YAMNET_INPUT_SIZE:
                analysis_chunk = buffer[:YAMNET_INPUT_SIZE]
                buffer = buffer[YAMNET_INPUT_SIZE:]
                
                # Inference - reshape to match expected input shape
                input_shape = interpreter.get_input_details()[0]['shape']
                if len(input_shape) == 1:
                    input_tensor = analysis_chunk
                else:
                    input_tensor = np.expand_dims(analysis_chunk, axis=0)
                
                interpreter.set_tensor(input_index, input_tensor)
                
                interpreter.invoke()
                scores = interpreter.get_tensor(output_index)[0]
                
                top_class_index = scores.argmax()
                
                if top_class_index < len(class_names):
                    prediction = class_names[top_class_index]
                    confidence = float(scores[top_class_index])

                    # Filter Logic: Ignore speech/silence, only send EVENTS
                    ignored = ["Silence", "Speech", "Inside, small room", "Inside, large room"]
                    if confidence > 0.30 and prediction not in ignored:
                         logger.info(f"Detected: {prediction} ({confidence:.2f})")
                         await ws.send_json({
                            "type": "environment",
                            "label": prediction,
                            "confidence": confidence
                        })
                    
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8001)