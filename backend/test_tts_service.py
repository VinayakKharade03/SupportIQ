import queue
import re
import sys
import threading
import time
import winsound

from app.services import tts

CANNED = [
    "I'm sorry, I don't have information on that. I can help with Bluetooth and "
    "charging issues, warranty questions, or placing an order, or I can connect "
    "you with our support team.",
    "Please log in first so I can manage your cart and orders.",
]

REPLIES = {
    "order": "Here's what I found:\n- Soundbar 2.1: Rs 6999\nTell me which one you'd like and I'll add it to your cart.",
    "bluetooth": (
        "To troubleshoot your Bluetooth connection issue with your earbuds, please follow these steps in order:\n"
        "1. Ensure the earbuds are charged. A low battery can prevent pairing.\n"
        "2. Turn off Bluetooth on your phone, wait 10 seconds, then turn it back on.\n"
        "3. Forget the device in your phone's Bluetooth settings and pair again."
    ),
    "canned": CANNED[0],
}

key = sys.argv[1] if len(sys.argv) > 1 else "order"
reply = REPLIES[key]

print("Cleaning checks:")
for raw in ["- Soundbar 2.1: Rs 6999", "2. Turn off Bluetooth, wait 10 seconds", "**Bold** text, Rs. 1,499 only"]:
    print(f"  {raw!r} -> {tts.clean_for_speech(raw)!r}")

t0 = time.time()
tts.warm_up()
n = tts.precache(CANNED)
print(f"\nTTS ready in {time.time() - t0:.1f}s, {n} fixed pieces cached\n")


def fake_llm_tokens(text):
    if key == "canned":
        yield text  # fixed replies arrive as a single token
        return
    for tok in re.findall(r"\s*\S+|\s+", text):
        time.sleep(0.02)
        yield tok


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
for text, wav in tts.speak_stream(fake_llm_tokens(reply)):
    print(f"[{now():5.2f}s] ready:   {text[:60]}")
    audio_q.put((text, wav))
audio_q.put(None)
p.join()
print(f"[{now():5.2f}s] done")
