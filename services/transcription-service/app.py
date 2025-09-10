import asyncio
import json
import os
from typing import Optional
import multiprocessing as mp

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import whisper

# Config
SAMPLE_RATE = 16000
DTYPE = np.int16
MODEL_NAME = os.environ.get("WHISPER_MODEL_NAME", "base")

MODE = "offline"
mode_lock = asyncio.Lock()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

def offline_worker_process(input_q: mp.Queue, output_q: mp.Queue, model_name: str):
    try:
        print(f"[worker] Loading Whisper model '{model_name}' (PID: {os.getpid()})")
        model = whisper.load_model(model_name)
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
                        result = model.transcribe(audio, language="en")
                        output_q.put(json.dumps({"final": result["text"]}))
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
                    result = model.transcribe(audio, language="en")
                    output_q.put(json.dumps({"partial": result["text"]}))
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
                args=(input_q_mp, output_q_mp, MODEL_NAME),
                daemon=True,
            )
            worker_process.start()

            async def poll_output_queue():
                loop = asyncio.get_running_loop()
                while True:
                    try:
                        item = await loop.run_in_executor(None, output_q_mp.get)
                    except Exception:
                        break
                    if item:
                        await ws.send_text(item)

            output_task = asyncio.create_task(poll_output_queue())

        while True:
            msg = await ws.receive()

            if msg["type"] == "websocket.receive":
                if "bytes" in msg:
                    chunk = msg["bytes"]
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
                    except json.JSONDecodeError:
                        pass

            elif msg["type"] in ("websocket.disconnect", "websocket.close"):
                break

    except WebSocketDisconnect:
        pass
    finally:
        try:
            if output_task:
                output_task.cancel()
            if worker_process and worker_process.is_alive():
                input_q_mp.put(b"__EOS__")
                worker_process.terminate()
                worker_process.join(timeout=1.0)
            if input_q_mp:
                input_q_mp.close()
            if output_q_mp:
                output_q_mp.close()
        except Exception:
            pass
        await ws.close()

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8002, log_level="info", reload=False)
