import base64
import json
import os
import re
import tempfile
import time
import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.ml.classifiers import classify
from app.ml.intent_router import classify_intent
from app.ml.model_loader import get_llm, get_whisper
from app.ml.product_search import build_product_index
from app.ml.rag import retrieve
from app.routers.support import MAX_DISTANCE, NO_ANSWER_REPLY, build_prompt_with_context
from app.services import tts
from app.services.order_agent import LOGIN_REPLY, get_optional_user, handle_order
from app.services.tickets import create_ticket, should_escalate

router = APIRouter()

VOICE_SYSTEM_PROMPT = (
    "You are a phone support agent for an audio electronics brand, speaking to a "
    "customer on a call. Reply in at most two short spoken sentences. Start with "
    "the answer itself, never with phrases like 'based on the context'. Never use "
    "lists, numbered steps, bullet points, markdown, or emojis. Use only the "
    "provided context. If the context does not cover the question, say so briefly."
)
# Repeated right after the question: small models follow the instruction closest to the answer
VOICE_REMINDER = (
    "\n\nReply in at most two short spoken sentences. Start directly with the answer: "
    "no lead-in, no steps, no lists."
)
VOICE_MAX_TOKENS = 120
MAX_SPOKEN_SENTENCES = 2
NOT_HEARD_REPLY = "Sorry, I didn't catch that. Could you say it again?"
ESCALATION_NOTE = "I've flagged this for priority review by our support team."

_SENTENCE_END = re.compile(r"(?<!\d)[.!?](?=\s|$)")  # list numbers like "1." don't count


def warm_up():
    """Loads models and pre-renders fixed replies. Runs in a background thread at startup."""
    steps = [
        ("Phi-3", get_llm),
        ("Whisper", get_whisper),
        ("product index", build_product_index),
        ("retrieval", lambda: retrieve("warm up", top_k=1)),
        ("TTS", tts.warm_up),
        ("TTS cache", lambda: tts.precache([NO_ANSWER_REPLY, LOGIN_REPLY, NOT_HEARD_REPLY])),
    ]
    for name, step in steps:
        start = time.time()
        try:
            step()
            print(f"[WARMUP] {name} ready in {time.time() - start:.1f}s")
        except Exception as e:
            print(f"[WARMUP] {name} failed: {e}")


def _event(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _transcribe(upload: UploadFile) -> str:
    temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.wav")
    try:
        with open(temp_path, "wb") as f:
            f.write(upload.file.read())
        start = time.time()
        segments = get_whisper().transcribe(temp_path, language="en")
        text = " ".join(s.text for s in segments).strip()
        print(f"[TIMING] Transcription: {time.time() - start:.3f}s")
        return text
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _llm_tokens(prompt: str):
    stream = get_llm().create_chat_completion(
        messages=[
            {"role": "system", "content": VOICE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt + VOICE_REMINDER},
        ],
        max_tokens=VOICE_MAX_TOKENS,
        stream=True,
    )
    spoken = ""
    try:
        for chunk in stream:
            token = chunk["choices"][0]["delta"].get("content", "")
            if not token:
                continue
            yield token
            spoken += token
            if len(_SENTENCE_END.findall(spoken)) >= MAX_SPOKEN_SENTENCES:
                break  # a phone answer stays short; stop generating here
    finally:
        stream.close()


def _with_note(tokens, note: str):
    """Speaks a closing line after the reply. The newline forces a sentence break."""
    yield from tokens
    yield "\n" + note


@router.post("/reply")
def voice_reply(
    file: UploadFile = File(...),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    text = _transcribe(file)
    intent = classify_intent(text) if text else "none"
    print(f"[VOICE] heard '{text}' -> {intent}")

    # Anything that needs the database session is computed here, before streaming starts.
    ticket_id = None
    if not text:
        tokens = [NOT_HEARD_REPLY]
    elif intent == "order":
        tokens = [handle_order(text, user, db)]
    else:
        sentiment, category = classify(text)
        escalate = should_escalate(sentiment, category)
        print(f"[CLASSIFY] sentiment={sentiment} category={category} escalate={escalate}")
        if escalate:
            ticket_id = create_ticket(db, user, text, sentiment, category, "voice").id
            print(f"[TICKET] opened #{ticket_id}")

        prompt, _, best_distance = build_prompt_with_context(text)
        if best_distance > MAX_DISTANCE:
            print(f"[RAG] best distance {best_distance:.3f} > {MAX_DISTANCE}, skipping LLM")
            tokens = [NO_ANSWER_REPLY]
        else:
            tokens = _llm_tokens(prompt)
        if ticket_id:
            tokens = _with_note(tokens, ESCALATION_NOTE)

    def events():
        yield _event({"transcript": text})
        start = time.time()
        first = True
        for sentence, wav in tts.speak_stream(tokens):
            if first:
                print(f"[TIMING] Voice first audio: {time.time() - start:.3f}s")
                first = False
            yield _event({"text": sentence, "audio": base64.b64encode(wav).decode()})
        print(f"[TIMING] Voice reply finished: {time.time() - start:.3f}s")
        if ticket_id:
            yield _event({"escalate": True, "ticket_id": ticket_id})
        yield _event({"done": True})

    return StreamingResponse(events(), media_type="text/event-stream")
