import os
import tempfile
import uuid

from fastapi import APIRouter, UploadFile, File

from app.schemas.chat import ChatResponse
from app.ml.model_loader import get_llm, get_whisper

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: dict):
    from app.schemas.chat import ChatRequest
    req = ChatRequest(**request)
    llm = get_llm()
    output = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": "You are a helpful customer support assistant for an audio electronics brand."},
            {"role": "user", "content": req.message},
        ],
        max_tokens=200,
    )
    reply_text = output["choices"][0]["message"]["content"]
    return ChatResponse(reply=reply_text)


@router.post("/voice-chat", response_model=ChatResponse)
async def voice_chat(file: UploadFile = File(...)):
    whisper = get_whisper()
    llm = get_llm()

    # Write to a short-lived temp file (Whisper needs a file path).
    # Deleted immediately after transcription — audio is never persisted.
    temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.wav")
    try:
        audio_bytes = await file.read()
        with open(temp_path, "wb") as f:
            f.write(audio_bytes)

        segments = whisper.transcribe(temp_path, language="en")
        transcribed_text = " ".join([s.text for s in segments]).strip()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    output = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": "You are a helpful customer support assistant for an audio electronics brand."},
            {"role": "user", "content": transcribed_text},
        ],
        max_tokens=200,
    )
    reply_text = output["choices"][0]["message"]["content"]
    return ChatResponse(reply=reply_text)
