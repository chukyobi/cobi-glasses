# services/sound-classifier/app.py

import logging
from typing import List

import numpy as np
import uvicorn
import webrtcvad
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Import shared configuration
from shared.config.audio_config import SAMPLE_RATE, FRAME_MS, VAD_AGGRESSIVENESS, SPEECH_RATIO_THRESHOLD

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# FastAPI app
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Initialize VAD
vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)

def split_frames(pcm16: bytes, sample_rate: int, frame_ms: int) -> List[bytes]:
    samples_per_frame = int(sample_rate * frame_ms / 1000)
    bytes_per_frame = samples_per_frame * 2  # int16
    frames = []
    for i in range(0, len(pcm16), bytes_per_frame):
        chunk = pcm16[i:i + bytes_per_frame]
        if len(chunk) == bytes_per_frame:
            frames.append(chunk)
    return frames

@app.websocket("/classify")
async def classify_socket(ws: WebSocket):
    await ws.accept()
    logging.info("WebSocket connection accepted.")
    try:
        while True:
            pcm_bytes = await ws.receive_bytes()
            frames = split_frames(pcm_bytes, SAMPLE_RATE, FRAME_MS)

            voiced = 0
            total = len(frames)
            for fr in frames:
                try:
                    if vad.is_speech(fr, SAMPLE_RATE):
                        voiced += 1
                except Exception as e:
                    logging.warning(f"Frame processing error: {e}")
                    continue

            ratio = (voiced / total) if total > 0 else 0.0
            label = "speech" if ratio >= SPEECH_RATIO_THRESHOLD and total > 0 else "non-speech"

            await ws.send_json({"label": label, "ratio": ratio})
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        logging.info("WebSocket connection closed.")

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=False)