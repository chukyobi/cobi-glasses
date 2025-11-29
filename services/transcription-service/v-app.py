import asyncio
import json
import os
import logging
from typing import Optional
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False
    print("ERROR: Vosk not installed. Run: pip install vosk")

# Configuration
SAMPLE_RATE = int(os.getenv("INPUT_SAMPLE_RATE", "16000"))
MODEL_PATH = os.getenv("VOSK_MODEL_PATH", "models/vosk-model-small-en-us-0.15")

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [VOSK-TRANSCRIBER] %(message)s")
logger = logging.getLogger("VoskTranscriber")

app = FastAPI(title="Vosk Real-Time Transcriber")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Global model (loaded once at startup)
vosk_model: Optional[Model] = None

def init_model():
    """Initialize Vosk model at startup."""
    global vosk_model
    
    if not VOSK_AVAILABLE:
        logger.critical("Vosk not installed!")
        return False
    
    if not os.path.exists(MODEL_PATH):
        logger.critical(f"Model not found at: {MODEL_PATH}")
        logger.info("Download a model from: https://alphacephei.com/vosk/models")
        logger.info("Example commands:")
        logger.info("  mkdir -p models")
        logger.info("  cd models")
        logger.info("  wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip")
        logger.info("  unzip vosk-model-small-en-us-0.15.zip")
        return False
    
    try:
        logger.info(f"Loading Vosk model from: {MODEL_PATH}")
        start_time = time.time()
        vosk_model = Model(MODEL_PATH)
        load_time = time.time() - start_time
        logger.info(f"✅ Model loaded successfully in {load_time:.2f}s")
        return True
    except Exception as e:
        logger.critical(f"Failed to load model: {e}")
        return False

@app.on_event("startup")
async def startup_event():
    """Load model when server starts."""
    success = init_model()
    if not success:
        logger.error("Server starting WITHOUT model - transcription will fail!")

@app.get("/health")
def health():
    return {
        "status": "ok" if vosk_model is not None else "error",
        "vosk_available": VOSK_AVAILABLE,
        "model_loaded": vosk_model is not None,
        "model_path": MODEL_PATH,
        "sample_rate": SAMPLE_RATE,
        "latency": "~0.2-0.5s"
    }

@app.get("/info")
def info():
    return {
        "service": "Vosk Real-Time Transcriber",
        "model_path": MODEL_PATH,
        "sample_rate": SAMPLE_RATE,
        "input_format": "PCM int16, mono",
        "features": [
            "True streaming (processes as audio arrives)",
            "Low latency (~200-500ms)",
            "Fully offline",
            "Partial results every ~0.1s"
        ]
    }

@app.websocket("/transcribe")
async def websocket_transcribe(ws: WebSocket):
    await ws.accept()
    logger.info("Client connected")
    
    if vosk_model is None:
        logger.error("Model not loaded - cannot transcribe")
        await ws.send_text(json.dumps({
            "error": "Vosk model not loaded. Check server logs."
        }))
        await ws.close(code=1011)
        return
    
    # Create recognizer for this connection
    recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)
    recognizer.SetWords(True)  # Get word-level timestamps
    
    logger.info("Recognizer created - ready for audio")
    
    bytes_received = 0
    last_partial_time = time.time()
    partial_interval = 0.3  # Send partials every 300ms
    
    try:
        while True:
            msg = await ws.receive()
            
            if msg["type"] == "websocket.receive":
                if "bytes" in msg:
                    audio_chunk = msg["bytes"]
                    bytes_received += len(audio_chunk)
                    
                    # Process audio chunk
                    if recognizer.AcceptWaveform(audio_chunk):
                        # Final result for this utterance
                        result = json.loads(recognizer.Result())
                        text = result.get("text", "").strip()
                        
                        if text:
                            logger.info(f"Final: {text}")
                            await ws.send_text(json.dumps({
                                "final": text,
                                "confidence": result.get("confidence", 1.0)
                            }))
                    else:
                        # Partial result (interim transcription)
                        current_time = time.time()
                        if current_time - last_partial_time >= partial_interval:
                            partial = json.loads(recognizer.PartialResult())
                            text = partial.get("partial", "").strip()
                            
                            if text:
                                logger.debug(f"Partial: {text}")
                                await ws.send_text(json.dumps({
                                    "partial": text
                                }))
                            
                            last_partial_time = current_time
                
                elif "text" in msg:
                    try:
                        data = json.loads(msg["text"])
                        
                        if data.get("event") == "eos":
                            logger.info("EOS received - finalizing")
                            
                            # Get final result from recognizer
                            final = json.loads(recognizer.FinalResult())
                            text = final.get("text", "").strip()
                            
                            if text:
                                logger.info(f"Final (EOS): {text}")
                                await ws.send_text(json.dumps({
                                    "final": text,
                                    "eos": True
                                }))
                            
                            break
                            
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON decode error: {e}")
            
            elif msg["type"] in ("websocket.disconnect", "websocket.close"):
                logger.info("WebSocket disconnect signal")
                break
    
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Error during transcription: {e}", exc_info=True)
    finally:
        logger.info(f"Session ended. Processed {bytes_received} bytes ({bytes_received/SAMPLE_RATE/2:.1f}s of audio)")
        
        if ws.client_state.name != "DISCONNECTED":
            await ws.close()

if __name__ == "__main__":
    if not VOSK_AVAILABLE:
        print("\n" + "="*80)
        print("ERROR: Vosk is not installed!")
        print("="*80)
        print("\nInstall it with:")
        print("  pip install vosk")
        print("\nThen download a model:")
        print("  mkdir -p models")
        print("  cd models")
        print("  wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip")
        print("  unzip vosk-model-small-en-us-0.15.zip")
        print("="*80 + "\n")
    
    uvicorn.run("app:app", host="0.0.0.0", port=8002, log_level="info")