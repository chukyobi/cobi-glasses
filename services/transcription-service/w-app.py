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

# faster-whisper only (no fallback)
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError as e:
    print(f"ERROR: faster-whisper not installed. Install with: pip install av faster-whisper")
    print(f"Import error details: {e}")
    FASTER_WHISPER_AVAILABLE = False

# WebRTC VAD for speech detection
try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False

# Configuration
try:
    from shared.config.audio_config import SAMPLE_RATE as CFG_SR, DTYPE as CFG_DT, MODEL_NAME as CFG_MODEL
    SAMPLE_RATE = int(CFG_SR)
    DTYPE = CFG_DT
    MODEL_NAME = CFG_MODEL
except Exception:
    SAMPLE_RATE = int(os.getenv("INPUT_SAMPLE_RATE", "16000"))
    DTYPE = os.getenv("DTYPE", "int16")
    MODEL_NAME = os.getenv("WHISPER_MODEL", "base")

MODE = os.getenv("MODE", "offline")
mode_lock = asyncio.Lock()
translate_enabled = mp.Value('b', False)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [TRANSCRIBER] [%(levelname)s] %(message)s")
logger = logging.getLogger("TranscriberService")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Initialize VAD
if VAD_AVAILABLE:
    vad = webrtcvad.Vad(2)
    logger.info("WebRTC VAD initialized (aggressiveness: 2)")
else:
    logger.warning("WebRTC VAD not available - accepting all audio")

def is_speech(audio_chunk: bytes) -> bool:
    """30ms VAD check on raw PCM int16 bytes."""
    if not VAD_AVAILABLE:
        return True
    frame_duration_ms = 30
    bytes_per_frame = int(SAMPLE_RATE * frame_duration_ms / 1000) * 2
    if len(audio_chunk) < bytes_per_frame:
        return False
    try:
        return vad.is_speech(audio_chunk[:bytes_per_frame], SAMPLE_RATE)
    except Exception as e:
        logger.warning(f"VAD error: {e}")
        return True

# ────────────────────────────────────────────────────────────────────────────────
# Audio Helpers
# ────────────────────────────────────────────────────────────────────────────────
def int16_bytes_to_float32(chunk_bytes: bytes) -> np.ndarray:
    """Convert PCM int16 bytes to float32 array normalized to [-1, 1]."""
    arr = np.frombuffer(chunk_bytes, dtype=np.int16).astype(np.float32)
    return arr / 32768.0

def float32_to_wav_bytes(wave_f32: np.ndarray, sample_rate: int) -> bytes:
    """Convert float32 array to WAV bytes."""
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
# Offline Worker Process (faster-whisper only)
# ────────────────────────────────────────────────────────────────────────────────
def offline_worker_process(input_q: mp.Queue, output_q: mp.Queue, model_name: str, translate_flag: Any, sr: int):
    """Worker process that runs Whisper transcription."""
    try:
        # Import in worker context
        try:
            from faster_whisper import WhisperModel as FW_Model
            print(f"[worker-{os.getpid()}] ✅ faster-whisper imported successfully")
        except ImportError as e:
            error_msg = f"faster-whisper not available in worker: {e}. Install: pip install av faster-whisper"
            print(f"[worker-{os.getpid()}] ❌ {error_msg}")
            output_q.put(json.dumps({"error": error_msg}))
            return
        
        # Load model
        model_dir = os.getenv("WHISPER_MODEL_DIR")
        device = os.getenv("WHISPER_DEVICE", "cpu")
        compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        
        if model_dir and os.path.exists(model_dir):
            print(f"[worker-{os.getpid()}] Loading model from local: {model_dir}")
            model = FW_Model(model_dir, device=device, compute_type=compute_type)
        else:
            print(f"[worker-{os.getpid()}] Downloading model '{model_name}' from Hugging Face...")
            model = FW_Model(model_name, device=device, compute_type=compute_type)
        
        print(f"[worker-{os.getpid()}] ✅ Model loaded successfully")

        # Buffer management
        buf = np.zeros((0,), dtype=np.float32)
        PARTIAL_SECONDS = float(os.getenv("PARTIAL_SECONDS", "2.0"))
        MIN_SAMPLES = int(float(os.getenv("MIN_SAMPLES_SEC", "0.5")) * sr)

        # Main processing loop
        while True:
            try:
                item = input_q.get(timeout=1.0)
            except Exception:
                continue

            # Handle EOS (end of stream)
            if isinstance(item, bytes) and item == b"__EOS__":
                print(f"[worker-{os.getpid()}] Received EOS signal")
                
                # Final transcription of remaining buffer
                if buf.size >= MIN_SAMPLES:
                    try:
                        wav_bytes = float32_to_wav_bytes(buf, sr)
                        task_type = "translate" if translate_flag.value else "transcribe"
                        
                        segments, info = model.transcribe(io.BytesIO(wav_bytes), task=task_type)
                        text = " ".join([seg.text for seg in segments]).strip()
                        
                        if text:
                            output_q.put(json.dumps({"final": text, "language": info.language}))
                            print(f"[worker-{os.getpid()}] Final: {text}")
                        
                    except Exception as e:
                        error_msg = f"Final transcription error: {e}"
                        output_q.put(json.dumps({"error": error_msg}))
                        print(f"[worker-{os.getpid()}] ❌ {error_msg}")
                
                break  # Exit worker loop

            # Handle audio chunks
            if isinstance(item, bytes):
                f32 = int16_bytes_to_float32(item)
                if f32.size > 0:
                    buf = np.concatenate([buf, f32])
                    print(f"[worker-{os.getpid()}] Buffer: {buf.size} samples ({buf.size/sr:.2f}s)")

            # Partial transcription when buffer is full enough
            if buf.size >= int(PARTIAL_SECONDS * sr):
                try:
                    wav_bytes = float32_to_wav_bytes(buf, sr)
                    task_type = "translate" if translate_flag.value else "transcribe"
                    
                    print(f"[worker-{os.getpid()}] Running transcription on {buf.size/sr:.2f}s of audio...")
                    segments, info = model.transcribe(io.BytesIO(wav_bytes), task=task_type, language=None)
                    text = " ".join([seg.text for seg in segments]).strip()
                    
                    if text:
                        output_q.put(json.dumps({"partial": text, "language": info.language}))
                        print(f"[worker-{os.getpid()}] Partial: {text}")
                    
                except Exception as e:
                    error_msg = f"Partial transcription error: {e}"
                    output_q.put(json.dumps({"error": error_msg}))
                    print(f"[worker-{os.getpid()}] ❌ {error_msg}")

                # Keep 1 second overlap for context
                overlap = int(1.0 * sr)
                buf = buf[-overlap:] if buf.size > overlap else np.zeros((0,), dtype=np.float32)

        print(f"[worker-{os.getpid()}] Shutting down gracefully")
        
    except Exception as e:
        error_msg = f"Worker process crashed: {e}"
        output_q.put(json.dumps({"error": error_msg}))
        print(f"[worker-{os.getpid()}] ❌ Critical error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            input_q.close()
            output_q.close()
        except Exception:
            pass

# ────────────────────────────────────────────────────────────────────────────────
# FastAPI Endpoints
# ────────────────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok" if FASTER_WHISPER_AVAILABLE else "error",
        "mode": MODE,
        "sample_rate": SAMPLE_RATE,
        "faster_whisper": FASTER_WHISPER_AVAILABLE,
        "vad": VAD_AVAILABLE,
        "message": "Ready" if FASTER_WHISPER_AVAILABLE else "Install faster-whisper: pip install av faster-whisper"
    }

@app.websocket("/transcribe")
async def websocket_transcribe(ws: WebSocket):
    await ws.accept()
    logger.info("Client connected to /transcribe")
    
    # Check if faster-whisper is available
    if not FASTER_WHISPER_AVAILABLE:
        error_msg = "faster-whisper not installed. Run: pip install av faster-whisper"
        logger.error(error_msg)
        await ws.send_text(json.dumps({"error": error_msg}))
        await ws.close(code=1011)
        return
    
    worker_process: Optional[mp.Process] = None
    input_q_mp: Optional[mp.Queue] = None
    output_q_mp: Optional[mp.Queue] = None
    output_task: Optional[asyncio.Task] = None

    try:
        # Start offline worker
        logger.info("Starting offline transcription worker...")
        input_q_mp = mp.Queue(maxsize=64)
        output_q_mp = mp.Queue(maxsize=64)
        
        worker_process = mp.Process(
            target=offline_worker_process,
            args=(input_q_mp, output_q_mp, MODEL_NAME, translate_enabled, SAMPLE_RATE),
            daemon=True,
        )
        worker_process.start()
        logger.info(f"Worker process started (PID: {worker_process.pid})")

        # Task to forward worker output to WebSocket
        async def poll_output_queue():
            loop = asyncio.get_running_loop()
            while True:
                try:
                    item = await loop.run_in_executor(None, output_q_mp.get)
                    if item:
                        await ws.send_text(item)
                        logger.info(f"Sent to client: {item[:100]}")
                except Exception as e:
                    logger.error(f"Output queue error: {e}")
                    break

        output_task = asyncio.create_task(poll_output_queue())

        # Main message loop
        while True:
            msg = await ws.receive()

            if msg["type"] == "websocket.receive":
                if "bytes" in msg:
                    chunk = msg["bytes"]
                    logger.debug(f"Received {len(chunk)} bytes")
                    
                    if is_speech(chunk):
                        logger.debug("Speech detected")
                        await asyncio.get_running_loop().run_in_executor(
                            None, lambda: input_q_mp.put(chunk)
                        )
                    else:
                        logger.debug("No speech detected")
                        
                elif "text" in msg:
                    try:
                        data = json.loads(msg["text"])
                        
                        if data.get("event") == "eos":
                            logger.info("Received EOS - finalizing transcription")
                            await asyncio.get_running_loop().run_in_executor(
                                None, lambda: input_q_mp.put(b"__EOS__")
                            )
                            await asyncio.sleep(1.5)
                            break
                            
                        elif data.get("event") == "toggle_translate":
                            translate_enabled.value = bool(data.get("enabled", False))
                            status = "enabled" if translate_enabled.value else "disabled"
                            logger.info(f"Translation {status}")
                            await ws.send_text(json.dumps({"info": f"Translation {status}"}))
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON decode error: {e}")

            elif msg["type"] in ("websocket.disconnect", "websocket.close"):
                logger.info("WebSocket disconnect signal")
                break

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        logger.info("Cleaning up...")
        try:
            if output_task:
                output_task.cancel()
                try:
                    await output_task
                except asyncio.CancelledError:
                    pass

            if worker_process and worker_process.is_alive():
                logger.info("Terminating worker process...")
                if input_q_mp:
                    try:
                        input_q_mp.put(b"__EOS__")
                    except Exception:
                        pass
                worker_process.terminate()
                worker_process.join(timeout=2.0)
                if worker_process.is_alive():
                    worker_process.kill()

            if input_q_mp:
                input_q_mp.close()
            if output_q_mp:
                output_q_mp.close()

            if ws.client_state.name != "DISCONNECTED":
                await ws.close()

        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        logger.info("Cleanup complete")

if __name__ == "__main__":
    if not FASTER_WHISPER_AVAILABLE:
        print("\n" + "="*80)
        print("ERROR: faster-whisper is not installed!")
        print("="*80)
        print("\nInstall it with:")
        print("  pip install av faster-whisper")
        print("\nOr if you're on macOS and need ffmpeg:")
        print("  brew install ffmpeg")
        print("  pip install av faster-whisper")
        print("="*80 + "\n")
    
    uvicorn.run("app:app", host="0.0.0.0", port=8002, log_level="info", reload=False)