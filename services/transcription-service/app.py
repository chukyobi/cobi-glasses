"""
service/transcriber_mp.py

Multiprocess transcriber service:
- FastAPI handles websockets and REST endpoints.
- For offline mode: a dedicated multiprocessing.Process is spawned per WS connection.
  That process loads the faster-whisper model (so model load doesn't block the main loop).
- For online mode: proxy audio to a remote STT websocket (REMOTE_STT_WS).
- The worker communicates using multiprocessing.Queue for audio (bytes) and results (JSON strings).
"""

import asyncio
import json
import os
from typing import Optional
import multiprocessing as mp
import time

import aiohttp
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Try import faster-whisper; if unavailable we'll surface an error on offline usage.
try:
    from faster_whisper import WhisperModel
    FAST_WHISPER_AVAILABLE = True
except Exception:
    FAST_WHISPER_AVAILABLE = False

# Config
SAMPLE_RATE = 16000
DTYPE = np.int16

# Offline model settings (tweak for Pi)
MODEL_NAME = os.environ.get("OFFLINE_MODEL", "tiny.en")
COMPUTE_TYPE = os.environ.get("COMPUTE_TYPE", "int8")  # int8 recommended on CPU for smaller footprint

# Remote STT for online mode
REMOTE_STT_WS = os.environ.get("REMOTE_STT_WS", "ws://127.0.0.1:9002/transcribe")

# Modes
MODE = "offline"  # default; can switch via REST API
mode_lock = asyncio.Lock()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# -------------------------------
# Worker process target for offline transcription
# -------------------------------
def offline_worker_process(input_q: mp.Queue, output_q: mp.Queue, model_name: str, compute_type: str):
    """
    Runs in a separate process. Loads the faster-whisper model and loops:
      - reads raw PCM bytes from input_q
      - accumulates into a numpy buffer
      - periodically runs model.transcribe and puts results (JSON strings) into output_q
    Protocol:
      - Input: bytes (raw int16 PCM). Special sentinel b"__EOS__" signals end-of-stream and triggers final flush then exit.
      - Output: JSON string messages with {"partial": "..."} or {"final": "..."} or {"error": "..."}
    """
    try:
        if not FAST_WHISPER_AVAILABLE:
            output_q.put(json.dumps({"error": "faster-whisper not installed in worker process"}))
            return

        # Load model (this usually takes most of the time, done inside worker process)
        print(f"[worker] Loading model {model_name} compute_type={compute_type} (PID: {os.getpid()})")
        model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
        print("[worker] Model loaded")

        # buffer parameters
        SAMPLE_RATE_LOCAL = SAMPLE_RATE
        buf = np.zeros((0,), dtype=DTYPE)
        last_emit = 0.0
        PARTIAL_SECONDS = 1.5   # how many seconds before producing a partial
        FINAL_SECONDS = 3.0     # flush final on EOS
        MIN_SAMPLES = int(0.3 * SAMPLE_RATE_LOCAL)

        while True:
            try:
                item = input_q.get(timeout=1.0)
            except Exception:
                # timeout - check continue
                item = None

            if item is None:
                # nothing received during this period
                # continue wait
                continue

            if isinstance(item, bytes) and item == b"__EOS__":
                # final flush and exit
                if buf.size >= MIN_SAMPLES:
                    try:
                        # convert to float32 normalized to [-1,1]
                        audio_float = (buf.astype(np.float32) / 32768.0)
                        segments, _ = model.transcribe(audio_float, beam_size=1, language="en")
                        for seg in segments:
                            output_q.put(json.dumps({"final": seg.text}))
                    except Exception as e:
                        output_q.put(json.dumps({"error": f"final transcription error: {str(e)}"}))
                break

            # append raw PCM bytes to buffer
            if isinstance(item, bytes):
                arr = np.frombuffer(item, dtype=DTYPE)
                if arr.size > 0:
                    buf = np.concatenate([buf, arr])

            # emit partials if buffer large enough
            if buf.size >= int(PARTIAL_SECONDS * SAMPLE_RATE_LOCAL):
                try:
                    audio_float = (buf.astype(np.float32) / 32768.0)
                    segments, _ = model.transcribe(audio_float, beam_size=1, language="en")
                    combined = " ".join([s.text for s in segments]).strip()
                    if combined:
                        output_q.put(json.dumps({"partial": combined}))
                except Exception as e:
                    output_q.put(json.dumps({"error": f"partial transcription error: {str(e)}"}))

                # keep last 1s for context
                overlap = int(1.0 * SAMPLE_RATE_LOCAL)
                if buf.size > overlap:
                    buf = buf[-overlap:]
                else:
                    buf = np.zeros((0,), dtype=DTYPE)

        print("[worker] exiting")
    except Exception as e:
        output_q.put(json.dumps({"error": f"worker process crash: {str(e)}"}))
    finally:
        # ensure worker exits cleanly
        try:
            input_q.close()
            output_q.close()
        except Exception:
            pass

# -------------------------------
# REST endpoints for mode control
# -------------------------------
@app.post("/set_mode/{mode}")
async def set_mode(mode: str):
    mode = mode.lower()
    if mode not in ("offline", "online"):
        return {"error": "mode must be 'offline' or 'online'"}
    async with mode_lock:
        global MODE
        MODE = mode
    return {"mode": MODE}

@app.get("/get_mode")
async def get_mode():
    return {"mode": MODE}

# -------------------------------
# Helper: proxy audio to remote STT (online mode)
# -------------------------------
async def proxy_to_remote(remote_ws_url: str, audio_queue: asyncio.Queue, ws_client: WebSocket):
    """
    Connect to remote websocket STT service and proxy bytes:
    - Read from audio_queue (asyncio.Queue)
    - send bytes to remote websocket
    - forward any remote text messages to ws_client
    """
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.ws_connect(remote_ws_url, timeout=60) as remote_ws:
                async def forward_remote():
                    async for msg in remote_ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                await ws_client.send_text(msg.data)
                            except Exception:
                                pass
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            try:
                                await ws_client.send_bytes(msg.data)
                            except Exception:
                                pass
                forward_task = asyncio.create_task(forward_remote())

                while True:
                    chunk = await audio_queue.get()
                    if chunk is None:
                        # sentinel -> send EOS and stop
                        try:
                            await remote_ws.send_str(json.dumps({"event": "eos"}))
                        except Exception:
                            pass
                        break
                    await remote_ws.send_bytes(chunk)

                forward_task.cancel()
    except Exception as e:
        # notify client about proxy issues
        try:
            await ws_client.send_text(json.dumps({"error": f"remote proxy error: {str(e)}"}))
        except Exception:
            pass

# -------------------------------
# WebSocket endpoint
# -------------------------------
@app.websocket("/transcribe")
async def websocket_transcribe(ws: WebSocket):
    """
    Accepts binary PCM int16 bytes from client.
    - If MODE == offline: spawn a worker process and use mp.Queues to send/receive.
    - If MODE == online: set up asyncio.Queue and proxy to REMOTE_STT_WS.
    Control: client may send {"event":"eos"} to flush and end.
    """
    await ws.accept()
    worker_process: Optional[mp.Process] = None
    input_q_mp: Optional[mp.Queue] = None
    output_q_mp: Optional[mp.Queue] = None
    output_task: Optional[asyncio.Task] = None
    proxy_task: Optional[asyncio.Task] = None
    async_audio_queue: Optional[asyncio.Queue] = None

    try:
        async with mode_lock:
            current_mode = MODE

        if current_mode == "offline":
            if not FAST_WHISPER_AVAILABLE:
                await ws.send_text(json.dumps({"error": "Offline model not available. Install faster-whisper."}))
                await ws.close()
                return

            # Create mp queues and spawn worker process
            input_q_mp = mp.Queue(maxsize=32)
            output_q_mp = mp.Queue(maxsize=32)
            worker_process = mp.Process(
                target=offline_worker_process,
                args=(input_q_mp, output_q_mp, MODEL_NAME, COMPUTE_TYPE),
                daemon=True,
            )
            worker_process.start()

            # Task that polls output_q_mp and forwards messages to websocket client
            async def poll_output_queue():
                loop = asyncio.get_running_loop()
                while True:
                    # run blocking get in executor
                    try:
                        item = await loop.run_in_executor(None, output_q_mp.get)
                    except Exception:
                        break
                    if item is None:
                        continue
                    try:
                        await ws.send_text(item)
                    except Exception:
                        break

            output_task = asyncio.create_task(poll_output_queue())

        else:
            # online proxy path
            async_audio_queue = asyncio.Queue(maxsize=128)
            proxy_task = asyncio.create_task(proxy_to_remote(REMOTE_STT_WS, async_audio_queue, ws))

        # Receive loop
        while True:
            msg = await ws.receive()

            if msg["type"] == "websocket.receive":
                if "bytes" in msg:
                    chunk = msg["bytes"]
                    if current_mode == "offline":
                        # place into mp queue in executor to avoid blocking event loop if queue is full
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(None, lambda q, c: q.put(c), input_q_mp, chunk)
                    else:
                        await async_audio_queue.put(chunk)
                elif "text" in msg:
                    # parse control messages
                    try:
                        data = json.loads(msg["text"])
                        if data.get("event") == "eos":
                            if current_mode == "offline":
                                # send sentinel and wait for worker to flush
                                await asyncio.get_running_loop().run_in_executor(None, lambda q: q.put(b"__EOS__"), input_q_mp)
                                # wait short while for outputs to flush
                                await asyncio.sleep(0.5)
                                # let worker exit naturally; join
                                if worker_process:
                                    # give worker a bit to finish
                                    worker_process.join(timeout=2.0)
                            else:
                                await async_audio_queue.put(None)  # sentinel for proxy
                                if proxy_task:
                                    await proxy_task
                            break
                        else:
                            # ignore unknown control messages
                            pass
                    except json.JSONDecodeError:
                        # ignore
                        pass

            elif msg["type"] == "websocket.disconnect":
                break
            elif msg["type"] == "websocket.close":
                break

    except WebSocketDisconnect:
        pass
    finally:
        # cleanup
        try:
            if output_task:
                output_task.cancel()
            if proxy_task:
                proxy_task.cancel()
            if worker_process and worker_process.is_alive():
                try:
                    input_q_mp.put(b"__EOS__")
                except Exception:
                    pass
                worker_process.terminate()
                worker_process.join(timeout=1.0)
            if input_q_mp:
                try:
                    input_q_mp.close()
                except Exception:
                    pass
            if output_q_mp:
                try:
                    output_q_mp.close()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            await ws.close()
        except Exception:
            pass

# -------------------------------
# Run server
# -------------------------------
if __name__ == "__main__":
    uvicorn.run("transcriber_mp:app", host="0.0.0.0", port=8002, log_level="info", reload=False)
