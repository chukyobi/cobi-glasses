import asyncio
import json
import os
import tempfile
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import subprocess

SAMPLE_RATE = 16000
DTYPE = np.int16
MODEL_PATH = os.environ.get("WHISPER_CPP_MODEL", "/home/pi/whisper.cpp/models/ggml-small.bin")
WHISPER_CPP_BIN = os.environ.get("WHISPER_CPP_BIN", "/home/pi/whisper.cpp/main")

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

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
                    arr = np.frombuffer(chunk, dtype=DTYPE)
                    if arr.size > 0:
                        buf = np.concatenate([buf, arr])
                    # Partial transcription every 2 seconds
                    if buf.size >= int(2.0 * SAMPLE_RATE):
                        text = await transcribe_with_whisper_cpp(buf)
                        await ws.send_text(json.dumps({"partial": text}))
                        # Keep last 1 second for overlap
                        overlap = int(1.0 * SAMPLE_RATE)
                        buf = buf[-overlap:] if buf.size > overlap else np.zeros((0,), dtype=DTYPE)
                elif "text" in msg:
                    try:
                        data = json.loads(msg["text"])
                        if data.get("event") == "eos":
                            if buf.size > 0:
                                text = await transcribe_with_whisper_cpp(buf)
                                await ws.send_text(json.dumps({"final": text}))
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

async def transcribe_with_whisper_cpp(buf: np.ndarray) -> str:
    # Save buffer as temporary WAV file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        import soundfile as sf
        sf.write(tmp_wav.name, buf.astype(np.float32) / 32768.0, SAMPLE_RATE)
        tmp_wav.flush()
        # Run whisper.cpp
        cmd = [
            WHISPER_CPP_BIN,
            "-m", MODEL_PATH,
            "-f", tmp_wav.name,
            "-nt",  # no timestamps
            "-l", "en"
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            # Parse output (whisper.cpp prints transcript to stdout)
            lines = result.stdout.splitlines()
            transcript = "\n".join([line for line in lines if line.strip()])
            return transcript.strip()
        except Exception as e:
            return f"[error] {str(e)}"
        finally:
            os.remove(tmp_wav.name)

if __name__ == "__main__":
    uvicorn.run("raspi_stt_service:app", host="0.0.0.0", port=9002, log_level="info")