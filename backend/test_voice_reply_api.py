import base64
import io
import json
import queue
import sys
import threading
import time
import winsound

import httpx
import numpy as np
import soundfile as sf

from app.services import tts

QUERY = " ".join(sys.argv[1:]) or "my earbuds wont connect to bluetooth"
URL = "http://127.0.0.1:8000/voice/reply"


def make_query_wav(text):
    wav = tts.synthesize(text)
    audio, sr = sf.read(io.BytesIO(wav), dtype="float32")
    n = int(len(audio) * 16000 / sr)
    audio16 = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio)
    buf = io.BytesIO()
    sf.write(buf, audio16, 16000, format="WAV", subtype="PCM_16")
    return buf.getvalue()


print("Preparing spoken query...")
query_wav = make_query_wav(QUERY)
print(f"Query: {QUERY}\n")

audio_q = queue.Queue()
t_start = time.time()


def now():
    return time.time() - t_start


def player():
    first, last_end = True, None
    while True:
        item = audio_q.get()
        if item is None:
            return
        text, wav = item
        t = now()
        if first:
            print(f"[{t:5.2f}s] >>> FIRST SOUND")
            first = False
        elif last_end is not None and t - last_end > 0.2:
            print(f"[{t:5.2f}s] gap of {t - last_end:.2f}s before this piece")
        print(f"[{t:5.2f}s] playing: {text}")
        winsound.PlaySound(wav, winsound.SND_MEMORY)
        last_end = now()


p = threading.Thread(target=player)
p.start()

with httpx.stream(
    "POST", URL, files={"file": ("query.wav", query_wav, "audio/wav")}, timeout=None
) as r:
    r.raise_for_status()
    for line in r.iter_lines():
        if not line.startswith("data: "):
            continue
        data = json.loads(line[6:])
        if "transcript" in data:
            print(f"[{now():5.2f}s] heard: {data['transcript']!r}")
        elif data.get("escalate"):
            print(f"[{now():5.2f}s] ESCALATED: ticket #{data['ticket_id']}")
        elif data.get("done"):
            break
        else:
            print(f"[{now():5.2f}s] received: {data['text'][:60]}")
            audio_q.put((data["text"], base64.b64decode(data["audio"])))

audio_q.put(None)
p.join()
print(f"[{now():5.2f}s] done")
