# services/audio-capture/client.py
import asyncio
import json
import logging
import queue
import signal
import sys
from typing import Optional

import numpy as np
import sounddevice as sd
import websockets

# ---------- Settings ----------
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_DURATION = 0.2  # seconds, 200ms blocks are a good balance
DTYPE = "int16"

CLASSIFIER_WS_URL = "ws://localhost:8001/classify"
TRANSCRIBE_WS_URL = "ws://localhost:8002/transcribe"

# If you want to print how loud the block is (debug)
PRINT_ENERGY = False
# ------------------------------

audio_q: "queue.Queue[np.ndarray]" = queue.Queue()
stop_flag = False

def audio_callback(indata, frames, time, status):
    if status:
        logging.warning(f"InputStream status: {status}")
    # Make a copy, push to thread-safe queue
    audio_q.put(indata.copy())

async def reader_task(ws_transcribe):
    """
    Read messages (partial/final transcripts) from transcription service and print them.
    """
    try:
        async for msg in ws_transcribe:
            try:
                data = json.loads(msg)
            except Exception:
                print(f"[transcriber] {msg}")
                continue

            if "partial" in data:
                print(f"\r[partial] {data['partial']}", end="", flush=True)
            if "final" in data:
                print(f"\n[final]   {data['final']}")
    except Exception as e:
        logging.error(f"Reader task error: {e}")

async def main():
    global stop_flag

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.info("Starting audio-capture client. Ctrl+C to stop.")

    # Connect websockets
    async with websockets.connect(CLASSIFIER_WS_URL, max_size=None) as ws_classifier, \
               websockets.connect(TRANSCRIBE_WS_URL, max_size=None) as ws_transcribe:

        # Kick off a task to read transcripts
        reader = asyncio.create_task(reader_task(ws_transcribe))

        # Setup sounddevice stream
        blocksize = int(SAMPLE_RATE * BLOCK_DURATION)
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=blocksize,
            callback=audio_callback,
        )
        stream.start()

        loop = asyncio.get_running_loop()

        def handle_sigint(*_):
            global stop_flag 
            stop_flag = True

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, handle_sigint)
            except NotImplementedError:
                # Windows
                pass

        try:
            while not stop_flag:
                # Pull a block from the queue (200ms of int16 PCM)
                block = await loop.run_in_executor(None, audio_q.get)
                if block is None:
                    continue

                if PRINT_ENERGY:
                    energy = float(np.mean(block.astype(np.float32) ** 2))
                    print(f"\n[energy] {energy:.1f}")

                # Send block to classifier
                await ws_classifier.send(block.tobytes())
                cls_msg = await ws_classifier.recv()
                cls = json.loads(cls_msg)
                label = cls.get("label", "non-speech")

                if label == "speech":
                    # Forward same PCM block to the transcription service
                    await ws_transcribe.send(block.tobytes())
                else:
                    # Optionally notify transcription service that this is silence
                    # (not required, but you can send a small control json if you implement it on server)
                    pass

                await asyncio.sleep(0)  # yield

        finally:
            stream.stop()
            stream.close()
            # Graceful close of transcription websocket (signal end of stream)
            try:
                await ws_transcribe.send(json.dumps({"event": "eos"}))
            except Exception:
                pass
            reader.cancel()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
