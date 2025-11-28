
from faster_whisper import WhisperModel
import os

# Choose model size: "tiny", "base", "small", "medium", "large-v2"
model_name = "base"

# Directory to store the model
#download_dir = os.path.abspath("C:/Users/bvnx/Documents/school/cobi-glasses/models/faster-whisper-base")
download_dir = os.path.abspath("/Users/mac/documents/devwork/school/cobi-glasses/models/faster-whisper-base")
os.makedirs(download_dir, exist_ok=True)

print(f"Downloading Faster-Whisper model '{model_name}' to {download_dir}...")
model = WhisperModel(model_name, device="cpu", download_root=download_dir)
print("Download complete!")
