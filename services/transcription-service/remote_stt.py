"""
service/remote_stt_server.py

A minimal STT websocket server that loads a larger Whisper model on GPU (device='cuda')
and transcribes incoming PCM bytes streaming back partial/final JSON messages.

This should run on a more powerful server (GPU) for online mode.
"""

import asyncio
import json
import os
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# faster-whisper
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
DTYPE = np.int16

MODEL_NAME = os.environ.get("REMOTE_MODEL", "base.en")  # choose a larger model on GPU
DEVICE = os.environ.get("REMOTE_DEVICE", "cuda")       # 'cuda' on GPU server
BEAM_SIZE = int(os.environ.get("BEAM_SIZE", "5"))

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

print(f"[remote_stt] loading model {MODEL_NAME} on {DEVICE} ...")
model = WhisperModel(MODEL_NAME, device=DEVICE, compute_type="float16" if DEVICE == "cuda" else "int8")
print("[remote_stt] model loaded")


@app.websocket("/transcribe")
async def ws_transcribe(ws: WebSocket):
    await ws.accept()
    buf = np.zeros((0,), dtype=DTYPE)
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.receive":
                if "bytes" in msg:
                    chunk = msg["bytes"]
                    if chunk == b"":
                        continue
                    arr = np.frombuffer(chunk, dtype=DTYPE)
                    if arr.size > 0:
                        buf = np.concatenate([buf, arr])
                    # simple streaming policy: when buffer > 1.5s, do a partial decode
                    if buf.size >= int(1.5 * SAMPLE_RATE):
                        audio_float = (buf.astype(np.float32) / 32768.0)
                        def _transcribe():
                            segments, _ = model.transcribe(audio_float, beam_size=BEAM_SIZE, language="en")
                            return [seg.text for seg in segments]
                        loop = asyncio.get_running_loop()
                        texts = await loop.run_in_executor(None, _transcribe)
                        combined = " ".join(texts).strip()
                        await ws.send_text(json.dumps({"partial": combined}))
                        # retain last second for overlap
                        overlap = int(1.0 * SAMPLE_RATE)
                        if buf.size > overlap:
                            buf = buf[-overlap:]
                        else:
                            buf = np.zeros((0,), dtype=DTYPE)

                elif "text" in msg:
                    try:
                        data = json.loads(msg["text"])
                        if data.get("event") == "eos":
                            if buf.size > 0:
                                audio_float = (buf.astype(np.float32) / 32768.0)
                                def _final():
                                    segments, _ = model.transcribe(audio_float, beam_size=BEAM_SIZE, language="en")
                                    return [seg.text for seg in segments]
                                loop = asyncio.get_running_loop()
                                finals = await loop.run_in_executor(None, _final)
                                for s in finals:
                                    await ws.send_text(json.dumps({"final": s}))
                            break
                    except json.JSONDecodeError:
                        pass
            elif msg["type"] in ("websocket.disconnect", "websocket.close"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await ws.close()
        except Exception:
            pass


if __name__ == "__main__":
    uvicorn.run("remote_stt_server:app", host="0.0.0.0", port=9002, log_level="info")
