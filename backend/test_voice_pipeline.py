import sounddevice as sd
import scipy.io.wavfile as wavfile
import numpy as np
import time

DURATION = 5  # seconds
SAMPLE_RATE = 16000  # Whisper expects 16kHz

print(f"Recording for {DURATION} seconds... speak now!")
audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
sd.wait()
print("Recording finished.")

wavfile.write("test_audio.wav", SAMPLE_RATE, audio)
print("Saved to test_audio.wav")

# --- Transcribe with Whisper ---
from pywhispercpp.model import Model

print("\nLoading Whisper...")
whisper_model = Model("small")

print("Transcribing...")
start = time.time()
segments = whisper_model.transcribe("test_audio.wav")
transcribed_text = " ".join([seg.text for seg in segments]).strip()
print(f"Transcribed in {time.time() - start:.2f}s")
print(f"You said: \"{transcribed_text}\"")

# --- Send to Phi-3-mini ---
from llama_cpp import Llama

print("\nLoading Phi-3-mini...")
llm = Llama(model_path="models/phi-3-mini-q4.gguf", n_gpu_layers=-1, n_ctx=2048, verbose=False)

print("Generating response...")
start = time.time()
output = llm.create_chat_completion(
    messages=[
        {"role": "system", "content": "You are a helpful customer support assistant for an audio electronics brand."},
        {"role": "user", "content": transcribed_text},
    ],
    max_tokens=150,
)
elapsed = time.time() - start
response_text = output["choices"][0]["message"]["content"]

print(f"\nAgent response (generated in {elapsed:.2f}s):")
print(response_text)
