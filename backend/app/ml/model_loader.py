from llama_cpp import Llama
from pywhispercpp.model import Model as WhisperModel

_llm = None
_whisper = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = Llama(
            model_path="models/phi-3-mini-q4.gguf",
            n_gpu_layers=-1,
            n_ctx=2048,
            verbose=False,
        )
    return _llm


def get_whisper():
    global _whisper
    if _whisper is None:
        _whisper = WhisperModel("small")
    return _whisper
