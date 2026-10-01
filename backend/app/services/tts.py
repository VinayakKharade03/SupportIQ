import io
import queue
import re
import threading
from typing import Iterable, Iterator, Optional, Tuple

import numpy as np
import soundfile as sf
from kokoro import KPipeline

SAMPLE_RATE = 24000
SPEED = 1.0
MIN_CHARS = 25   # shortest piece worth speaking on its own
FIRST_MAX = 120   # if the first clause runs long, cut the first piece near here

# language -> (Kokoro lang_code, voice). Hindi gets added here later.
VOICES = {"en": ("a", "af_heart")}
DEFAULT_LANG = "en"

_CLAUSE = re.compile(r"(?<=[,;:.!?])\s+|\s*\n+\s*")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\s*\n+\s*")
_BARE_MARKER = re.compile(r"\d+[.)]|[-*\u2022]")

_pipelines = {}
_cache = {}
_lock = threading.Lock()


def clean_for_speech(text: str) -> str:
    text = re.sub(r"(?m)^\s*(?:[-*\u2022]|\d+[.)])\s+", "", text)  # list markers at the start
    text = re.sub(r"[*#`_]", "", text)
    text = re.sub(r"\bRs\.?\s*(\d[\d,]*)", r"\1 rupees", text)
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    return re.sub(r"\s+", " ", text).strip()


class SpeechChunker:
    """Turns streamed text into speakable pieces: a short first piece, then sentences."""

    def __init__(self):
        self.buffer = ""
        self.pending = ""
        self.first_done = False

    def _add(self, raw: str):
        piece = clean_for_speech(raw)
        if not piece or _BARE_MARKER.fullmatch(piece):
            return []
        if self.pending:
            sep = " " if self.pending[-1] in ".!?:;," else ". "
            piece = f"{self.pending}{sep}{piece}"
            self.pending = ""
        if len(piece) >= MIN_CHARS:
            self.first_done = True
            return [piece]
        self.pending = piece
        return []

    def feed(self, token: str):
        self.buffer += token
        out = []
        while True:
            parts = (_SENTENCE if self.first_done else _CLAUSE).split(self.buffer, maxsplit=1)
            if len(parts) < 2:
                break
            piece, self.buffer = parts
            out += self._add(piece)
        if not self.first_done and len(self.buffer) >= FIRST_MAX:
            cut = self.buffer.rfind(" ", 0, FIRST_MAX)
            if cut > MIN_CHARS:
                piece, self.buffer = self.buffer[:cut], self.buffer[cut:].lstrip()
                out += self._add(piece)
        return out

    def flush(self):
        out = self._add(self.buffer) if self.buffer.strip() else []
        self.buffer = ""
        if self.pending:
            out.append(self.pending)
            self.pending = ""
        return out


def _pipeline(lang: str) -> KPipeline:
    if lang not in _pipelines:
        code, _ = VOICES[lang]
        _pipelines[lang] = KPipeline(lang_code=code, repo_id="hexgrad/Kokoro-82M", device="cpu")
    return _pipelines[lang]


def _render(text: str, lang: str) -> Optional[bytes]:
    _, voice = VOICES[lang]
    with _lock:
        pipe = _pipeline(lang)
        chunks = [a for _, _, a in pipe(text, voice=voice, speed=SPEED) if a is not None]
    if not chunks:
        return None
    audio = np.concatenate([a.numpy() if hasattr(a, "numpy") else a for a in chunks])
    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def synthesize(text: str, lang: str = DEFAULT_LANG) -> Optional[bytes]:
    """Returns WAV bytes for one speakable piece (from the cache if it was pre-rendered)."""
    return _cache.get((lang, text)) or _render(text, lang)


def warm_up(lang: str = DEFAULT_LANG) -> None:
    """Loads the model and runs one throwaway synthesis so the first real request is fast."""
    _render("Hello there.", lang)


def precache(texts: Iterable[str], lang: str = DEFAULT_LANG) -> int:
    """Pre-renders fixed replies so they play instantly. Returns the cache size."""
    for text in texts:
        chunker = SpeechChunker()
        for piece in chunker.feed(text) + chunker.flush():
            if (lang, piece) not in _cache:
                wav = _render(piece, lang)
                if wav:
                    _cache[(lang, piece)] = wav
    return len(_cache)


def speak_stream(tokens: Iterable[str], lang: str = DEFAULT_LANG) -> Iterator[Tuple[str, bytes]]:
    """Reads text tokens (e.g. from the LLM) and yields (text, wav_bytes) one piece at a time.

    Chunking runs in a background thread so the LLM keeps generating while we synthesize.
    """
    q: queue.Queue = queue.Queue()

    def produce():
        try:
            chunker = SpeechChunker()
            for token in tokens:
                for piece in chunker.feed(token):
                    q.put(piece)
            for piece in chunker.flush():
                q.put(piece)
        except Exception as e:  # surface errors in the consuming thread
            q.put(e)
        finally:
            q.put(None)

    threading.Thread(target=produce, daemon=True).start()
    while True:
        item = q.get()
        if item is None:
            return
        if isinstance(item, Exception):
            raise item
        wav = synthesize(item, lang)
        if wav:
            yield item, wav
