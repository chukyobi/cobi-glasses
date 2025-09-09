
import math
from typing import List

import numpy as np
import uvicorn
import webrtcvad
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

SAMPLE_RATE = 16000
FRAME_MS = 20  
VAD_AGGRESSIVENESS = 2  
SPEECH_RATIO_THRESHOLD = 0.5  

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

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
                except Exception:
                    # If frame is malformed, skip
                    pass

            ratio = (voiced / total) if total > 0 else 0.0
            label = "speech" if ratio >= SPEECH_RATIO_THRESHOLD and total > 0 else "non-speech"

            await ws.send_json({"label": label, "ratio": ratio})
    except Exception:
        # Client disconnected or error; just close
        pass

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=False)
