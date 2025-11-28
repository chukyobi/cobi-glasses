
import asyncio
import io
import json
import os
import wave
import multiprocessing as mp
import logging
from typing import Optional, Any

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Try imports with graceful fallbacks
try:
    from faster_whisper import WhisperModel  # type: ignore
    FASTER_WHISPER_AVAILABLE = True
except Exception:
    FASTER_WHISPER_AVAILABLE = False

try:
    import webrtcvad  # type: ignore
    VAD_AVAILABLE = True
except Exception:
    VAD_AVAILABLE = False

# Import shared configuration or use defaults
try:
    from shared.config.audio_config import SAMPLE_RATE as CFG_SR, DTYPE as CFG_DT, MODEL_NAME as CFG_MODEL  # type: ignore
    SAMPLE_RATE = int(CFG_SR)
    DTYPE = CFG_DT
    MODEL_NAME = CFG_MODEL
except Exception:
    SAMPLE_RATE = int(os.getenv("INPUT_SAMPLE_RATE", "16000"))
    DTYPE = os.getenv("DTYPE", "int16")
    MODEL_NAME = os.getenv("WHISPER_MODEL", "small")  # faster-whisper / openai-whisper model id

MODE = os.getenv("MODE", "offline")  # "offline" or "cloud"
mode_lock = asyncio.Lock()
translate_enabled = mp.Value('b', False)  # Shared flag for translation toggle

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [TRANSCRIBER] [%(levelname)s] %(message)s")
logger = logging.getLogger("TranscriberService")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Initialize VAD (if available)
if VAD_AVAILABLE:
    vad = webrtcvad.Vad(2)  # 0..3 (aggressiveness)

def is_speech(audio_chunk: bytes) -> bool:
    """30ms VAD gate over raw PCM int16 bytes (mono)."""
    if not VAD_AVAILABLE:
        return True  # if no VAD, accept everything
    frame_duration_ms = 30
    bytes_per_frame = int(SAMPLE_RATE * frame_duration_ms / 1000) * 2  # 16-bit mono
    if len(audio_chunk) < bytes_per_frame:
        return False
    return vad.is_speech(audio_chunk[:bytes_per_frame], SAMPLE_RATE)

# ────────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────────
def int16_bytes_to_float32(chunk_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32)
    return arr / 32768.0

def float32_to_wav_bytes(wave_f32: np.ndarray, sample_rate: int) -> bytes:
    wave_clipped = np.clip(wave_f32, -1.0, 1.0)
    wave_i16 = (wave_clipped * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(wave_i16.tobytes())
    return buf.getvalue()

# ────────────────────────────────────────────────────────────────────────────────
# Offline worker (multiprocess)
# ────────────────────────────────────────────────────────────────────────────────
def offline_worker_process(input_q: mp.Queue, output_q: mp.Queue, model_name: str, translate_flag: Any, sr: int):
    try:
        # Resolve model path (prefer local folder if present)
        default_local = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../models/faster-whisper-base"))
        local_path = os.getenv("WHISPER_MODEL_DIR", default_local)

        model = None
        if FASTER_WHISPER_AVAILABLE:
            if os.path.exists(local_path):
                print(f"[worker] Loading faster-whisper from local path '{local_path}' (PID: {os.getpid()})")
                model = WhisperModel(local_path, device=os.getenv("WHISPER_DEVICE", "cpu"),
                                     compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
            else:
                print(f"[worker] Local path not found; loading faster-whisper model '{model_name}'.")
                model = WhisperModel(model_name, device=os.getenv("WHISPER_DEVICE", "cpu"),
                                     compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
        else:
            import whisper  # openai-whisper fallback
            print(f"[worker] Loading openai-whisper model '{model_name}' (PID: {os.getpid()})")
            model = whisper.load_model(model_name)

        print("[worker] Model loaded")

        buf = np.zeros((0,), dtype=np.float32)
        PARTIAL_SECONDS = float(os.getenv("PARTIAL_SECONDS", "1.5"))
        MIN_SAMPLES = int(float(os.getenv("MIN_SAMPLES_SEC", "0.3")) * sr)

        # Main loop
        while True:
            try:
                item = input_q.get(timeout=1.0)
            except Exception:
                item = None

            if item is None:
                continue

            if isinstance(item, bytes) and item == b"__EOS__":
                # Final flush
                if buf.size >= MIN_SAMPLES:
                    try:
                        wav_bytes = float32_to_wav_bytes(buf, sr)
                        task_type = "translate" if translate_flag.value else "transcribe"
                        if FASTER_WHISPER_AVAILABLE:
                            segments, info = model.transcribe(io.BytesIO(wav_bytes), task=task_type)
                            text = "".join([seg.text for seg in segments]).strip()
                            output_q.put(json.dumps({"final": text, "language": info.language}))
                        else:
                            # openai-whisper expects a file path
                            import tempfile
                            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                                tmp.write(wav_bytes)
                                tmp.flush()
                                res = model.transcribe(tmp.name, task=task_type)
                            text = res.get("text", "").strip()
                            lang = res.get("language", "")
                            output_q.put(json.dumps({"final": text, "language": lang}))
                    except Exception as e:
                        output_q.put(json.dumps({"error": f"final transcription error: {str(e)}"}))
                break

            if isinstance(item, bytes):
                f32 = int16_bytes_to_float32(item)
                if f32.size > 0:
                    buf = np.concatenate([buf, f32])

            # Partial transcription chunk
            if buf.size >= int(PARTIAL_SECONDS * sr):
                try:
                    wav_bytes = float32_to_wav_bytes(buf, sr)
                    task_type = "translate" if translate_flag.value else "transcribe"
                    if FASTER_WHISPER_AVAILABLE:
                        segments, info = model.transcribe(io.BytesIO(wav_bytes), task=task_type)
                        text = "".join([seg.text for seg in segments]).strip()
                        output_q.put(json.dumps({"partial": text, "language": info.language}))
                    else:
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                            tmp.write(wav_bytes)
                            tmp.flush()
                            res = model.transcribe(tmp.name, task=task_type)
                        text = res.get("text", "").strip()
                        lang = res.get("language", "")
                        output_q.put(json.dumps({"partial": text, "language": lang}))
                except Exception as e:
                    output_q.put(json.dumps({"error": f"partial transcription error: {str(e)}"}))

                # Keep 1 second overlap for continuity
                overlap = int(1.0 * sr)
                buf = buf[-overlap:] if buf.size > overlap else np.zeros((0,), dtype=np.float32)

        print("[worker] exiting")
    except Exception as e:
        output_q.put(json.dumps({"error": f"worker process crash: {str(e)}"}))
    finally:
        try:
            input_q.close()
            output_q.close()
        except Exception:
            pass

# ────────────────────────────────────────────────────────────────────────────────
# FastAPI WebSocket
# ────────────────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "mode": MODE,
        "sample_rate": SAMPLE_RATE,
        "faster_whisper": FASTER_WHISPER_AVAILABLE,
        "vad": VAD_AVAILABLE
    }

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
                args=(input_q_mp, output_q_mp, MODEL_NAME, translate_enabled, SAMPLE_RATE),
                daemon=True,
            )
            worker_process.start()

            async def poll_output_queue():
                loop = asyncio.get_running_loop()
                while True:
                    try:
                        item = await loop.run_in_executor(None, output_q_mp.get)
                    except Exception as e:
                        logger.error(f"Output queue polling error: {e}")
                        break
                    if item:
                        await ws.send_text(item)

            output_task = asyncio.create_task(poll_output_queue())

        elif current_mode == "cloud":
            logger.info("Cloud transcription mode is not yet implemented.")
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
                        logger.warning(f"JSON decode error: {e}")

            elif msg["type"] in ("websocket.disconnect", "websocket.close"):
                break

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
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

            if ws.client_state.name != "DISCONNECTED":
                await ws.close()

        except Exception as e:
            logger.error(f"Cleanup error: {e}")

if __name__ == "__main__":
    uvicorn.run("transcriber_app:app", host="0.0.0.0", port=8002, log_level="info", reload=False)
