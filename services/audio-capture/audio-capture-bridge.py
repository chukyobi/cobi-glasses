
import asyncio
import json
import logging
import queue
import threading
import numpy as np
import sounddevice as sd
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Optional

# --- Configuration ---
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION = 0.5
BLOCK_DURATION = CHUNK_DURATION
DTYPE = "int16"

CLASSIFIER_WS_URL = "ws://localhost:8001/classify"
TRANSCRIBE_WS_URL = "ws://localhost:8002/transcribe"

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [BRIDGE] [%(levelname)s] %(message)s")
logger = logging.getLogger("AudioBridge")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- Global State ---
stop_event = threading.Event()
audio_q: queue.Queue[np.ndarray] = queue.Queue()
control_ws_ref: Optional[WebSocket] = None
main_event_loop: Optional[asyncio.AbstractEventLoop] = None


def audio_callback(indata, frames, time, status):
    """Callback for sounddevice. Runs in a separate C-thread."""
    if status:
        logger.warning(f"InputStream status: {status}")
    if not stop_event.is_set():
        try:
            audio_q.put_nowait(indata.copy())
        except queue.Full:
            logger.warning("Audio queue full, dropping frame")


async def send_to_react(message: str):
    """Thread-safe helper to send message to React on the Main Loop."""
    if control_ws_ref and main_event_loop and control_ws_ref.client_state.name != "DISCONNECTED":
        asyncio.run_coroutine_threadsafe(control_ws_ref.send_text(message), main_event_loop)


# ✅ Updated process_audio_block using exception-driven approach
async def process_audio_block(block, ws_c, ws_t):
    try:
        await asyncio.gather(
            ws_c.send(block.tobytes()),
            ws_t.send(block.tobytes())
        )
        return True
    except websockets.exceptions.ConnectionClosed:
        logger.error("Connection closed while sending block")
        return False
    except Exception as e:
        logger.error(f"Error sending block: {e}")
        return False


async def listen_to_service(ws_source, tag):
    """Listens to a service and forwards results to React."""
    try:
        async for msg in ws_source:
            await send_to_react(msg)
            if tag == "Classifier" and "environment" in msg:
                logger.info(f"Forwarded Environmental Sound: {msg}")
    except Exception as e:
        logger.warning(f"Listener for {tag} stopped: {e}")


def mic_stream_thread_entry():
    asyncio.run(mic_stream_logic())


async def mic_stream_logic():
    logger.info("Starting Microphone Stream Thread...")
    ws_t = None
    ws_c = None

    try:
        # Connect to services
        ws_t = await websockets.connect(TRANSCRIBE_WS_URL, max_size=None, ping_interval=20, ping_timeout=60)
        ws_c = await websockets.connect(CLASSIFIER_WS_URL, max_size=None, ping_interval=20, ping_timeout=60)
        logger.info("Connected to Data APIs (8001 & 8002).")

        # Start listeners
        task_t = asyncio.create_task(listen_to_service(ws_t, "Transcriber"))
        task_c = asyncio.create_task(listen_to_service(ws_c, "Classifier"))

        blocksize = int(SAMPLE_RATE * BLOCK_DURATION)
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, blocksize=blocksize, callback=audio_callback):
            logger.info("Microphone input started.")
            while not stop_event.is_set():
                try:
                    block = audio_q.get_nowait()
                    success = await process_audio_block(block, ws_c, ws_t)
                    if not success:
                        logger.error("Failed to send audio block, stopping stream")
                        break
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue
                except Exception as e:
                    logger.error(f"Stream loop error: {e}")
                    break

        # Cleanup
        logger.info("Sending EOS...")
        try:
            await ws_t.send(json.dumps({"event": "eos"}))
        except Exception:
            pass

        task_t.cancel()
        task_c.cancel()
        await asyncio.gather(task_t, task_c, return_exceptions=True)

    except Exception as e:
        logger.error(f"Critical Thread Error: {e}")
    finally:
        if ws_t:
            await ws_t.close()
        if ws_c:
            await ws_c.close()
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
                        audio_q.get()
                    mic_thread = threading.Thread(target=mic_stream_thread_entry)
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
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
