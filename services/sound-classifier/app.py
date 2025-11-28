
import os
import csv
import json
import logging
from typing import Optional, List

import numpy as np
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# ────────────────────────────────────────────────────────────────────────────────
# Runtime selection: Prefer LiteRT (ai-edge-litert), fallback to TensorFlow Lite
# ────────────────────────────────────────────────────────────────────────────────
RUNTIME_NAME = None

try:
    # LiteRT (successor to TensorFlow Lite) — recommended on Linux/embedded
    from ai_edge_litert.interpreter import Interpreter as LiteInterpreter  # type: ignore
    def make_interpreter(model_path: str):
        return LiteInterpreter(model_path=model_path)
    RUNTIME_NAME = "LiteRT (ai-edge-litert)"
except Exception:
    # Fallback to full TensorFlow's TFLite on platforms where LiteRT wheel isn't available (e.g., Windows)
    import tensorflow.lite as tflite  # type: ignore
    def make_interpreter(model_path: str):
        return tflite.Interpreter(model_path=model_path)
    RUNTIME_NAME = "TensorFlow Lite (tensorflow.lite)"

# ────────────────────────────────────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────────────────────────────────────
# If you have a global config, we’ll try to load SAMPLE_RATE from it; else 16000.
DEFAULT_SAMPLE_RATE = 16000
try:
    from shared.config.audio_config import SAMPLE_RATE  # type: ignore
    INPUT_SAMPLE_RATE = int(SAMPLE_RATE) or DEFAULT_SAMPLE_RATE
except Exception:
    INPUT_SAMPLE_RATE = DEFAULT_SAMPLE_RATE

MODEL_PATH = os.getenv("MODEL_PATH", "yamnet.tflite")
CLASS_MAP_PATH = os.getenv("CLASS_MAP_PATH", "yamnet_class_map.csv")

# YAMNet expects exactly 15,600 samples (0.975 s @ 16 kHz)
YAMNET_INPUT_SIZE = 15600
TARGET_SAMPLE_RATE = 16000

# Confidence threshold and ignored labels can be customized via env
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
    """
    Reads a YAMNet class map CSV. If not found or fails, returns a placeholder list.
    Expected format (common): header, then rows where label is at index 2.
    """
    if not os.path.isfile(csv_path):
        if expected_len:
            logger.warning(f"Class map CSV not found at '{csv_path}'. Using {expected_len} generic labels.")
            return [f"class_{i}" for i in range(expected_len)]
        logger.warning(f"Class map CSV not found at '{csv_path}'. Using generic labels with default length 521.")
        return [f"class_{i}" for i in range(521)]

    try:
        class_names: List[str] = []
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)  # skip header
            for row in reader:
                # Safest: try index 2 (common in YAMNet maps), fallback to last column if shorter
                label_idx = 2 if len(row) > 2 else (len(row) - 1 if len(row) > 0 else 0)
                class_names.append(row[label_idx])
        if expected_len and len(class_names) != expected_len:
            logger.warning(
                f"Class map length ({len(class_names)}) != model output length ({expected_len}). "
                "Using the first N or padding with generic labels."
            )
            if len(class_names) > expected_len:
                class_names = class_names[:expected_len]
            else:
                class_names += [f"class_{i}" for i in range(len(class_names), expected_len)]
        logger.info(f"Loaded {len(class_names)} audio classes from CSV.")
        return class_names
    except Exception as e:
        logger.error(f"Error reading class map CSV '{csv_path}': {e}")
        if expected_len:
            return [f"class_{i}" for i in range(expected_len)]
        return [f"class_{i}" for i in range(521)]


def resample_if_needed(wave: np.ndarray, from_sr: int, to_sr: int = TARGET_SAMPLE_RATE) -> np.ndarray:
    """
    Simple linear resampling (numpy.interp). For streaming chunks this is adequate.
    """
    if from_sr == to_sr or wave.size == 0:
        return wave.astype(np.float32)
    ratio = to_sr / float(from_sr)
    new_len = max(1, int(round(wave.size * ratio)))
    x_old = np.arange(wave.size)
    x_new = np.linspace(0, wave.size - 1, new_len)
    resampled = np.interp(x_new, x_old, wave).astype(np.float32)
    return resampled


def normalize_int16_to_float32(int16_pcm: bytes) -> np.ndarray:
    """
    Convert raw PCM int16 bytes -> float32 waveform in [-1, 1].
    """
    wave = np.frombuffer(int16_pcm, dtype=np.int16).astype(np.float32)
    return wave / 32768.0


# ────────────────────────────────────────────────────────────────────────────────
# Model setup (global interpreter & class names)
# ────────────────────────────────────────────────────────────────────────────────
interpreter = None
input_index = None
output_index = None
class_names: List[str] = []

def init_model():
    global interpreter, input_index, output_index, class_names

    if not os.path.isfile(MODEL_PATH):
        logger.critical(f"Model file not found at '{MODEL_PATH}'. Place 'yamnet.tflite' or set MODEL_PATH.")
        return

    logger.info(f"Runtime: {RUNTIME_NAME}")
    logger.info(f"Loading model from '{MODEL_PATH}' ...")
    try:
        interpreter = make_interpreter(MODEL_PATH)
        interpreter.allocate_tensors()

        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()

        # Expect first input to be mono waveform [1, 15600] float32
        input_index = input_details[0]["index"]
        output_index = output_details[0]["index"]

        logger.info(f"Model loaded. Input: shape={input_details[0]['shape']}, dtype={input_details[0]['dtype']}")
        logger.info(f"Model loaded. Output: shape={output_details[0]['shape']}, dtype={output_details[0]['dtype']}")

        # Output length (e.g., 521 for YAMNet)
        out_shape = output_details[0]["shape"]
        num_classes = int(out_shape[-1]) if out_shape is not None and len(out_shape) > 0 else 521

        # Load class names (or use placeholders matching the model’s output length)
        class_names = safe_read_classmap_csv(CLASS_MAP_PATH, expected_len=num_classes)

    except Exception as e:
        logger.critical(f"Failed to initialize interpreter: {e}")
        interpreter = None
        input_index = None
        output_index = None


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

@app.get("/info")
def info():
    return {
        "runtime": RUNTIME_NAME,
        "model_path": MODEL_PATH,
        "class_map_path": CLASS_MAP_PATH,
        "input_sample_rate": INPUT_SAMPLE_RATE,
        "target_sample_rate": TARGET_SAMPLE_RATE,
        "window_samples": YAMNET_INPUT_SIZE,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "ignored_labels_count": len(IGNORED_LABELS)
    }

# WebSocket for streaming audio classification
@app.websocket("/classify")
async def classify_socket(ws: WebSocket):
    await ws.accept()
    logger.info("Client connected to /classify")

    # If model failed to load, close connection immediately
    if interpreter is None or input_index is None or output_index is None:
        logger.error("Cannot classify: Interpreter not loaded.")
        await ws.close(code=1011)
        return

    # Continuous buffer in target sample rate
    buffer = np.zeros(0, dtype=np.float32)

    try:
        while True:
            data_bytes = await ws.receive_bytes()

            # 1) PCM int16 -> float32 waveform
            wave = normalize_int16_to_float32(data_bytes)

            # 2) Resample if incoming sample rate != 16 kHz
            wave = resample_if_needed(wave, from_sr=INPUT_SAMPLE_RATE, to_sr=TARGET_SAMPLE_RATE)

            # 3) Append to buffer and process fixed-size windows (0.975 s)
            buffer = np.concatenate((buffer, wave))

            while buffer.size >= YAMNET_INPUT_SIZE:
                # Slice the analysis window and advance buffer
                analysis_chunk = buffer[:YAMNET_INPUT_SIZE].astype(np.float32)
                buffer = buffer[YAMNET_INPUT_SIZE:]

                # Ensure shape [1, 15600]
                input_tensor = np.expand_dims(analysis_chunk, axis=0).astype(np.float32)

                # Set input, invoke, get scores
                interpreter.set_tensor(input_index, input_tensor)
                interpreter.invoke()
                scores = interpreter.get_tensor(output_index)[0]  # shape [num_classes]

                top_idx = int(np.argmax(scores))
                confidence = float(scores[top_idx])
                label = class_names[top_idx] if top_idx < len(class_names) else f"class_{top_idx}"

                # Filter low confidence or ignored labels
                if confidence >= CONFIDENCE_THRESHOLD and label not in IGNORED_LABELS:
                    logger.info(f"Detected: {label} ({confidence:.2f})")
                    await ws.send_json({
                        "type": "environment",
                        "label": label,
                        "confidence": confidence
                    })

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await ws.close(code=1011)
        except Exception:
            pass


if __name__ == "__main__":
    # Run: python app.py
    uvicorn.run("app:app", host="0.0.0.0", port=8001, log_level="info")
