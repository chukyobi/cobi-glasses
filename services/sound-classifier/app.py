import os
import csv
import json
import logging
import asyncio
from typing import Optional, List

import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# ────────────────────────────────────────────────────────────────────────────────
# Runtime selection
# ────────────────────────────────────────────────────────────────────────────────
RUNTIME_NAME = None

try:
    from ai_edge_litert.interpreter import Interpreter as LiteInterpreter
    def make_interpreter(model_path: str):
        return LiteInterpreter(model_path=model_path)
    RUNTIME_NAME = "LiteRT (ai-edge-litert)"
except Exception:
    import tensorflow.lite as tflite
    def make_interpreter(model_path: str):
        return tflite.Interpreter(model_path=model_path)
    RUNTIME_NAME = "TensorFlow Lite (tensorflow.lite)"

# ────────────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────────────
DEFAULT_SAMPLE_RATE = 16000
try:
    from shared.config.audio_config import SAMPLE_RATE
    INPUT_SAMPLE_RATE = int(SAMPLE_RATE) or DEFAULT_SAMPLE_RATE
except Exception:
    INPUT_SAMPLE_RATE = DEFAULT_SAMPLE_RATE

MODEL_PATH = os.getenv("MODEL_PATH", "yamnet.tflite")
CLASS_MAP_PATH = os.getenv("CLASS_MAP_PATH", "yamnet_class_map.csv")

# YAMNet expects exactly 15,600 samples (0.975 s @ 16 kHz)
YAMNET_INPUT_SIZE = 15600
TARGET_SAMPLE_RATE = 16000

# Confidence threshold and ignored labels
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.30"))
IGNORED_LABELS = set(
    json.loads(os.getenv("IGNORED_LABELS", '["Silence","Speech","Inside, small room","Inside, large room"]'))
)

# ────────────────────────────────────────────────────────────────────────────────
# Logging & FastAPI setup
# ────────────────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [CLASSIFIER] %(message)s")
logger = logging.getLogger("SoundClassifier")

app = FastAPI(title="YAMNet Sound Classifier", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# ────────────────────────────────────────────────────────────────────────────────
# Utilities
# ────────────────────────────────────────────────────────────────────────────────
def safe_read_classmap_csv(csv_path: str, expected_len: Optional[int] = None) -> List[str]:
    """Reads a YAMNet class map CSV."""
    if not os.path.isfile(csv_path):
        logger.warning(f"Class map CSV not found at '{csv_path}'. Using generic labels.")
        limit = expected_len if expected_len else 521
        return [f"class_{i}" for i in range(limit)]

    try:
        class_names: List[str] = []
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            # Skip header if present
            header = next(reader, None) 
            # Reset if header doesn't look like a header or logic requires
            # (YAMNet CSVs usually have a header)
            
            for row in reader:
                # YAMNet map format: index, mid, display_name
                label_idx = 2 if len(row) > 2 else (len(row) - 1 if len(row) > 0 else 0)
                class_names.append(row[label_idx])
                
        if expected_len and len(class_names) != expected_len:
            logger.warning(
                f"Class map length ({len(class_names)}) != model output length ({expected_len})."
            )
            if len(class_names) > expected_len:
                class_names = class_names[:expected_len]
            else:
                class_names += [f"class_{i}" for i in range(len(class_names), expected_len)]
        
        logger.info(f"Loaded {len(class_names)} audio classes from CSV.")
        return class_names
    except Exception as e:
        logger.error(f"Error reading class map CSV '{csv_path}': {e}")
        limit = expected_len if expected_len else 521
        return [f"class_{i}" for i in range(limit)]


def resample_if_needed(wave: np.ndarray, from_sr: int, to_sr: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """Simple linear resampling using numpy.interp."""
    if from_sr == to_sr or wave.size == 0:
        return wave.astype(np.float32)
    ratio = to_sr / float(from_sr)
    new_len = max(1, int(round(wave.size * ratio)))
    x_old = np.arange(wave.size)
    x_new = np.linspace(0, wave.size - 1, new_len)
    resampled = np.interp(x_new, x_old, wave).astype(np.float32)
    return resampled


def normalize_int16_to_float32(int16_pcm: bytes) -> np.ndarray:
    """Convert raw PCM int16 bytes -> float32 waveform in [-1, 1]."""
    wave = np.frombuffer(int16_pcm, dtype=np.int16).astype(np.float32)
    return wave / 32768.0


# ────────────────────────────────────────────────────────────────────────────────
# Model setup
# ────────────────────────────────────────────────────────────────────────────────
interpreter = None
input_index = None
output_index = None
class_names: List[str] = []

def init_model():
    global interpreter, input_index, output_index, class_names

    if not os.path.isfile(MODEL_PATH):
        logger.critical(f"Model file not found at '{MODEL_PATH}'.")
        return

    logger.info(f"Runtime: {RUNTIME_NAME}")
    logger.info(f"Loading model from '{MODEL_PATH}' ...")
    try:
        interpreter = make_interpreter(MODEL_PATH)
        interpreter.allocate_tensors()

        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        input_index = input_details[0]["index"]
        output_index = output_details[0]["index"]

        out_shape = output_details[0]["shape"]
        num_classes = int(out_shape[-1]) if out_shape is not None and len(out_shape) > 0 else 521

        class_names = safe_read_classmap_csv(CLASS_MAP_PATH, expected_len=num_classes)
        logger.info("Model and Class Map loaded successfully.")

    except Exception as e:
        logger.critical(f"Failed to initialize interpreter: {e}")
        interpreter = None


# Initialize at startup
init_model()

# ────────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ────────────────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok" if interpreter is not None else "error",
        "runtime": RUNTIME_NAME,
        "model_loaded": interpreter is not None
    }

@app.websocket("/classify")
async def classify_socket(ws: WebSocket):
    await ws.accept()
    logger.info("Client connected to /classify")

    if interpreter is None or input_index is None or output_index is None:
        logger.error("Cannot classify: Interpreter not loaded.")
        await ws.close(code=1011)
        return

    buffer = np.zeros(0, dtype=np.float32)

    try:
        while True:
            # 1. SMART RECEIVE: Timeout trick to keep Event Loop alive
            try:
                # Wait 10ms for data, then yield
                data_bytes = await asyncio.wait_for(ws.receive_bytes(), timeout=0.01)
            except asyncio.TimeoutError:
                await asyncio.sleep(0) # Yield control to Heartbeat
                continue

            # 2. Pre-processing
            # Convert PCM int16 -> float32
            wave = normalize_int16_to_float32(data_bytes)
            # Resample
            wave = resample_if_needed(wave, from_sr=INPUT_SAMPLE_RATE, to_sr=TARGET_SAMPLE_RATE)
            # Add to buffer
            buffer = np.concatenate((buffer, wave))

            # 3. Inference Loop
            # Process as many 0.975s windows as we have in the buffer
            while buffer.size >= YAMNET_INPUT_SIZE:
                analysis_chunk = buffer[:YAMNET_INPUT_SIZE].astype(np.float32)
                buffer = buffer[YAMNET_INPUT_SIZE:]

                # BLOCKING CALL: YAMNet Inference (~50ms on CPU)
                # This is where pings usually die.
                interpreter.set_tensor(input_index, analysis_chunk)
                interpreter.invoke() 
                scores = interpreter.get_tensor(output_index)
                
                # Handle output shape
                if scores.ndim > 1:
                    scores = scores[0]

                top_idx = int(np.argmax(scores))
                confidence = float(scores[top_idx])
                label = class_names[top_idx] if top_idx < len(class_names) else f"class_{top_idx}"

                # Filter and send
                if confidence >= CONFIDENCE_THRESHOLD and label not in IGNORED_LABELS:
                    logger.info(f"Detected: {label} ({confidence:.2f})")
                    await ws.send_json({
                        "type": "environment",
                        "label": label,
                        "confidence": confidence
                    })
                
                # CRITICAL FIX: Yield immediately after inference
                # This lets the server say "Pong" to any pending Pings.
                await asyncio.sleep(0)

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await ws.close(code=1011)
        except Exception:
            pass


if __name__ == "__main__":
    # We can now use defaults, or disable pings for extra safety
    # But with the 'await asyncio.sleep(0)' fix, defaults usually work.
    uvicorn.run("app:app", host="0.0.0.0", port=8001, log_level="info")