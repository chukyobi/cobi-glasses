import asyncio
import json
import os
import multiprocessing as mp
import logging
from typing import Optional
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from faster_whisper import WhisperModel
import webrtcvad

# Import shared configuration
from shared.config.audio_config import SAMPLE_RATE, DTYPE, MODEL_NAME
MODE = "offline"  # Can be "offline" or "cloud"
mode_lock = asyncio.Lock()
translate_enabled = mp.Value('b', False)  # Shared flag for translation toggle

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Initialize VAD
vad = webrtcvad.Vad(2)

def is_speech(audio_chunk: bytes) -> bool:
    frame_duration_ms = 30
    bytes_per_frame = int(SAMPLE_RATE * frame_duration_ms / 1000) * 2
    if len(audio_chunk) < bytes_per_frame:
        return False
    return vad.is_speech(audio_chunk[:bytes_per_frame], SAMPLE_RATE)

def offline_worker_process(input_q: mp.Queue, output_q: mp.Queue, model_name: str, translate_flag: mp.Value):
    try:
        print(f"[worker] Loading Faster-Whisper model '{model_name}' (PID: {os.getpid()})")
        model = WhisperModel(model_name, device="cpu")
        print("[worker] Model loaded")

        buf = np.zeros((0,), dtype=DTYPE)
        PARTIAL_SECONDS = 1.5
        MIN_SAMPLES = int(0.3 * SAMPLE_RATE)

        while True:
            try:
                item = input_q.get(timeout=1.0)
            except Exception:
                item = None

            if item is None:
                continue

            if isinstance(item, bytes) and item == b"__EOS__":
                if buf.size >= MIN_SAMPLES:
                    try:
                        audio = buf.astype(np.float32) / 32768.0
                        task_type = "translate" if translate_flag.value else "transcribe"
                        segments, info = model.transcribe(audio, task=task_type)
                        text = " ".join([seg.text for seg in segments])
                        output_q.put(json.dumps({"final": text, "language": info.language}))
                    except Exception as e:
                        output_q.put(json.dumps({"error": f"final transcription error: {str(e)}"}))
                break

            if isinstance(item, bytes):
                arr = np.frombuffer(item, dtype=DTYPE)
                if arr.size > 0:
                    buf = np.concatenate([buf, arr])

            if buf.size >= int(PARTIAL_SECONDS * SAMPLE_RATE):
                try:
                    audio = buf.astype(np.float32) / 32768.0
                    task_type = "translate" if translate_flag.value else "transcribe"
                    segments, info = model.transcribe(audio, task=task_type)
                    text = " ".join([seg.text for seg in segments])
                    output_q.put(json.dumps({"partial": text, "language": info.language}))
                except Exception as e:
                    output_q.put(json.dumps({"error": f"partial transcription error: {str(e)}"}))

                overlap = int(1.0 * SAMPLE_RATE)
                buf = buf[-overlap:] if buf.size > overlap else np.zeros((0,), dtype=DTYPE)

        print("[worker] exiting")
    except Exception as e:
        output_q.put(json.dumps({"error": f"worker process crash: {str(e)}"}))
    finally:
        try:
            input_q.close()
            output_q.close()
        except Exception:
            pass

@app.websocket("/transcribe")
async def websocket_transcribe(ws: WebSocket):
    await ws.accept()
    worker_process: Optional[mp.Process] = None
    input_q_mp: Optional[mp.Queue] = None
    output_q_mp: Optional[mp.Queue] = None
    output_task: Optional[asyncio.Task] = None

    try:
        async with mode_lock:
            current_mode = MODE

        if current_mode == "offline":
            input_q_mp = mp.Queue(maxsize=32)
            output_q_mp = mp.Queue(maxsize=32)
            worker_process = mp.Process(
                target=offline_worker_process,
                args=(input_q_mp, output_q_mp, MODEL_NAME, translate_enabled),
                daemon=True,
            )
            worker_process.start()

            async def poll_output_queue():
                loop = asyncio.get_running_loop()
                while True:
                    try:
                        item = await loop.run_in_executor(None, output_q_mp.get)
                    except Exception as e:
                        logging.error(f"Output queue polling error: {e}")
                        break
                    if item:
                        await ws.send_text(item)

            output_task = asyncio.create_task(poll_output_queue())

        elif current_mode == "cloud":
            logging.info("Cloud transcription mode is not yet implemented.")
            await ws.send_text(json.dumps({"info": "Cloud transcription mode is not yet available."}))

        while True:
            msg = await ws.receive()

            if msg["type"] == "websocket.receive":
                if "bytes" in msg:
                    chunk = msg["bytes"]
                    if is_speech(chunk):
                        await asyncio.get_running_loop().run_in_executor(None, lambda q, c: q.put(c), input_q_mp, chunk)
                elif "text" in msg:
                    try:
                        data = json.loads(msg["text"])
                        if data.get("event") == "eos":
                            await asyncio.get_running_loop().run_in_executor(None, lambda q: q.put(b"__EOS__"), input_q_mp)
                            await asyncio.sleep(0.5)
                            if worker_process:
                                worker_process.join(timeout=2.0)
                            break
                        elif data.get("event") == "toggle_translate":
                            translate_enabled.value = bool(data.get("enabled", False))
                            await ws.send_text(json.dumps({"info": f"Translation {'enabled' if translate_enabled.value else 'disabled'}"}))
                    except json.JSONDecodeError as e:
                        logging.warning(f"JSON decode error: {e}")

            elif msg["type"] in ("websocket.disconnect", "websocket.close"):
                break

    except WebSocketDisconnect:
        logging.info("WebSocket disconnected.")
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        try:
            if output_task:
                output_task.cancel()
                try:
                    await output_task
                except asyncio.CancelledError:
                    pass
            if worker_process and worker_process.is_alive():
                input_q_mp.put(b"__EOS__")
                worker_process.terminate()
                worker_process.join(timeout=1.0)
            if input_q_mp:
                input_q_mp.close()
            if output_q_mp:
                output_q_mp.close()
        except Exception as e:
            logging.error(f"Cleanup error: {e}")
        await ws.close()

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8002, log_level="info", reload=False)