# shared/config/audio_config.py

DURATION = 5  # seconds
SAMPLE_RATE = 16000  # Hz
CHANNELS = 1
CHUNK_DURATION = 1  # seconds
OUTPUT_DIR = "shared/audio_chunks"
OUTPUT_FILE = "captured_audio.wav"

# Classifier-specific settings
FRAME_MS = 20  # milliseconds
VAD_AGGRESSIVENESS = 2  # 0 (least aggressive) to 3 (most aggressive)
SPEECH_RATIO_THRESHOLD = 0.5  # ratio threshold for speech detection


# Transcription-specific
DTYPE = "int16"
MODEL_NAME = "base"  # Whisper model name
