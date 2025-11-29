import asyncio
import json
import logging
import queue
import threading
import os
from typing import Optional

import numpy as np
import sounddevice as sd
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# --- Configuration ---
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
CHANNELS = 1
CHUNK_DURATION = float(os.getenv("CHUNK_SECONDS", "0.5"))
BLOCK_DURATION = CHUNK_DURATION
DTYPE = "int16"

TRANSCRIBE_WS_URL = os.getenv("TRANSCRIBE_WS_URL", "ws://localhost:8002/transcribe")
CLASSIFIER_WS_URL = os.getenv("CLASSIFIER_WS_URL", "ws://localhost:8001/classify")

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [BRIDGE] [%(levelname)s] %(message)s")
logger = logging.getLogger("AudioBridge")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# --- Global State ---
stop_event = threading.Event()
audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=64)
control_ws_ref: Optional[WebSocket] = None
main_event_loop: Optional[asyncio.AbstractEventLoop] = None

def audio_callback(indata, frames, time, status):
    if status:
        logger.warning(f"InputStream status: {status}")
    if not stop_event.is_set():
        try:
            audio_q.put_nowait(indata.copy())
        except queue.Full:
            logger.warning("Audio queue full, dropping frame")

async def send_to_react(message: str):
    """Thread-safe helper to send message to the React client via /control."""
    if control_ws_ref and main_event_loop and control_ws_ref.client_state.name != "DISCONNECTED":
        asyncio.run_coroutine_threadsafe(control_ws_ref.send_text(message), main_event_loop)

async def process_audio_block(block, ws_t, ws_c):
    """Send audio block to BOTH transcriber and classifier"""
    audio_bytes = block.tobytes()
    
    # Send to both services, but don't fail if one is slow
    tasks = []
    if ws_t:
        tasks.append(ws_t.send(audio_bytes))
    if ws_c:
        tasks.append(ws_c.send(audio_bytes))
    
    if not tasks:
        return False
        
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Log errors but don't stop streaming unless both fail
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        for err in errors:
            logger.warning(f"Audio send warning: {err}")
    
    # Only fail if ALL sends failed
    return len(errors) < len(tasks)

async def listen_to_transcriber(ws_t):
    """Forward transcriber messages to React."""
    try:
        async for msg in ws_t:
            await send_to_react(msg)
            logger.info(f"[Bridge] Forwarded transcript: {msg[:120]}")
    except websockets.exceptions.ConnectionClosed as e:
        logger.warning(f"Transcriber connection closed: {e}")
    except Exception as e:
        logger.warning(f"Transcriber listener stopped: {e}")

async def listen_to_classifier(ws_c):
    """Forward classifier messages to React."""
    try:
        async for msg in ws_c:
            await send_to_react(msg)
            logger.info(f"[Bridge] Forwarded classification: {msg[:120]}")
    except websockets.exceptions.ConnectionClosed as e:
        logger.warning(f"Classifier connection closed: {e}")
    except Exception as e:
        logger.warning(f"Classifier listener stopped: {e}")

def mic_stream_thread_entry():
    asyncio.run(mic_stream_logic())

async def mic_stream_logic():
    logger.info("Starting Microphone Stream Thread...")
    ws_t = None
    ws_c = None
    task_t = None
    task_c = None

    try:
        # Connect to BOTH services with MUCH longer timeouts
        ws_t = await websockets.connect(
            TRANSCRIBE_WS_URL, 
            max_size=None, 
            ping_interval=None,  # Disable automatic pings from client side
            ping_timeout=None,   # Disable ping timeout
            close_timeout=10
        )
        logger.info("Connected to Transcriber (8002).")
        
        ws_c = await websockets.connect(
            CLASSIFIER_WS_URL, 
            max_size=None, 
            ping_interval=None, 
            ping_timeout=None,
            close_timeout=10
        )
        logger.info("Connected to Classifier (8001).")

        # Start listeners for both
        task_t = asyncio.create_task(listen_to_transcriber(ws_t))
        task_c = asyncio.create_task(listen_to_classifier(ws_c))

        # Start mic
        blocksize = int(SAMPLE_RATE * BLOCK_DURATION)
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, blocksize=blocksize, callback=audio_callback):
            logger.info("Microphone input started.")
            
            while not stop_event.is_set():
                try:
                    # 1. Get the data
                    block = audio_q.get_nowait()
                    
                    # 2. Send the data (Data Plane)
                    success = await process_audio_block(block, ws_t, ws_c)
                    
                    if not success:
                        logger.error("Audio send failed. Stopping stream.")
                        break
                    
                    # 3. THE SMART FIX: Explicit Context Switch (Control Plane)
                    # Force the loop to yield control. This allows the websocket library 
                    # to process incoming Pings (Heartbeats) from the server immediately.
                    await asyncio.sleep(0)
                        
                except queue.Empty:
                    # If no audio, sleep a tiny bit to save CPU
                    await asyncio.sleep(0.01)
                except Exception as e:
                    logger.error(f"Stream loop error: {e}")
                    break

        # Send EOS to transcriber (if still connected)
        logger.info("Sending EOS to transcriber...")
        try:
            if ws_t:
                await ws_t.send(json.dumps({"event": "eos"}))
        except Exception as e:
            logger.warning(f"Failed to send EOS: {e}")

        # Cancel listeners
        if task_t:
            task_t.cancel()
        if task_c:
            task_c.cancel()
        await asyncio.gather(task_t, task_c, return_exceptions=True)

    except Exception as e:
        logger.error(f"Critical mic thread error: {e}")
    finally:
        for ws in [ws_t, ws_c]:
            if ws:
                try:
                    await ws.close()
                except Exception:
                    pass
        logger.info("Microphone thread connections closed.")
        stop_event.clear()

@app.websocket("/control")
async def control_socket(ws: WebSocket):
    global control_ws_ref, main_event_loop
    await ws.accept()
    logger.info("React Control Client connected on Port 8000.")
    control_ws_ref = ws
    main_event_loop = asyncio.get_running_loop()

    mic_thread: Optional[threading.Thread] = None

    try:
        while True:
            data = await ws.receive_text()
            try:
                command = json.loads(data)
            except json.JSONDecodeError:
                continue

            if command.get("action") == "start":
                if mic_thread is None or not mic_thread.is_alive():
                    logger.info("Received START command.")
                    stop_event.clear()
                    while not audio_q.empty():
                        try:
                            audio_q.get_nowait()
                        except queue.Empty:
                            break
                    mic_thread = threading.Thread(target=mic_stream_thread_entry, daemon=True)
                    mic_thread.start()

            elif command.get("action") == "stop":
                logger.info("Received STOP command.")
                stop_event.set()
                if mic_thread:
                    mic_thread.join(timeout=2.0)

    except WebSocketDisconnect:
        logger.info("React Control Client disconnected.")
    except Exception as e:
        logger.error(f"Control WebSocket Error: {e}")
    finally:
        stop_event.set()
        if mic_thread and mic_thread.is_alive():
            mic_thread.join(timeout=2.0)
        control_ws_ref = None

if __name__ == "__main__":
    uvicorn.run("bridge_app:app", host="0.0.0.0", port=8000, workers=1)