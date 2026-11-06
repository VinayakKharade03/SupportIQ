import os
import time
import tempfile
import uuid
import json
import re

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.ml.model_loader import get_llm, get_whisper
from app.ml.rag import retrieve
from app.services.hinglish import to_english_query
from app.ml.intent_router import classify_intent
from app.ml.classifiers import classify
from app.services.order_agent import handle_order, get_optional_user
from app.services.tickets import create_ticket, should_escalate

router = APIRouter()

# Low-randomness decoding: factual answers, fewer self-contradictions
SAMPLING = {"temperature": 0.2, "top_p": 0.9, "repeat_penalty": 1.1}

SYSTEM_PROMPT = (
    "You are a helpful customer support assistant for an audio electronics brand. "
    "Use the provided context to answer accurately. If the context doesn't cover "
    "the question, say so honestly rather than guessing."
)

# FAISS L2 distance: lower = closer. Real questions scored <= 0.8, off-topic >= 1.78.
MAX_DISTANCE = 1.3
NO_ANSWER_REPLY = (
    "I'm sorry, I don't have information on that. I can help with Bluetooth and "
    "charging issues, warranty questions, or placing an order, or I can connect "
    "you with our support team."
)


CARE_NAME = "CARE"
CARE_PERSONA = (
    "You are CARE, a warm and calm customer support assistant for an audio electronics store. "
    "Always reply in English, in the first person, starting with the answer itself.\n"
    "Rules:\n"
    "- Use only the provided context. Never invent steps, features, numbers or brands.\n"
    "- If the context does not mention the topic at all, say: I don't have that detail.\n"
    "- If the context says something is absent, that is an answer. Give it.\n"
    "- Answer only what was asked, in at most two short sentences, or at most three short steps.\n"
    "- Always use the product's full name exactly as written in the context, brand included.\n"
    "- If the customer sounds upset, start with one short caring sorry, then give only the single most useful fix, and offer to help with the next step."
)
SYSTEM_PROMPT = CARE_PERSONA

FEWSHOT = [
    {"role": "user", "content": "Context:\n[Acme X1 - FAQ]\nThe Acme X1 has Bluetooth 5.0 and no aux input.\n\nCustomer question: does the Acme X1 have an aux port"},
    {"role": "assistant", "content": "No, the Acme X1 has no aux input. Connect it over Bluetooth."},
    {"role": "user", "content": "Context:\n[Acme X1 - FAQ]\nThe Acme X1 has Bluetooth 5.0 and no aux input.\n\nCustomer question: does the Acme X1 have NFC"},
    {"role": "assistant", "content": "I don't have that detail about NFC for the Acme X1."},
    {"role": "user", "content": "Context:\n[Acme X1 - FAQ]\nThe Acme X1 is rated IP67: submersion up to 1 metre for 30 minutes.\n\nCustomer question: can I use the Acme X1 underwater for 3 hours"},
    {"role": "assistant", "content": "Not for 3 hours. It is rated IP67, which covers up to 1 metre for 30 minutes."},
    {"role": "user", "content": "Context:\n[Acme X1 - Pairing]\nTake the Acme X1 out of its case. It flashes blue. Turn on Bluetooth on your phone and select Acme X1.\n\nCustomer question: how do I pair it"},
    {"role": "assistant", "content": "Take the Acme X1 out of its case, turn on Bluetooth on your phone, then select Acme X1 once it flashes blue."},
    {"role": "user", "content": "Context:\n[Acme X1 - Troubleshooting]\nHold the power button for 10 seconds to reset the Acme X1.\n\nCustomer question: this is useless, it keeps freezing"},
    {"role": "assistant", "content": "I'm really sorry, that sounds frustrating. Hold the power button for 10 seconds to reset the Acme X1, and tell me if it still freezes."},
]
NO_ANSWER_REPLY = (
    "I'm sorry, I don't have information on that yet. I can help with your products, "
    "Bluetooth and charging problems, warranty questions, or placing an order, "
    "or I can connect you with our support team."
)


def greeting_for(user=None) -> str:
    """Time-of-day greeting, with the first name when the user is logged in."""
    from datetime import datetime

    hour = datetime.now().hour
    part = "morning" if hour < 12 else ("afternoon" if hour < 17 else "evening")
    full = (getattr(user, "full_name", None) or "").strip()
    name = full.split()[0] if full else ""
    who = f", {name}" if name else ""
    return (
        f"Good {part}{who}. I'm CARE. I can help with your products, troubleshooting, "
        "warranty questions, or placing an order. What can I do for you?"
    )


GREETING_REPLY = (
    "Hello! I can help with your products, Bluetooth or charging issues, "
    "warranty questions, or placing an order. What can I do for you?"
)
REFUND_REPLY = (
    "I'm sorry about this. I've passed your refund request to our support team "
    "for priority review, and they will follow up with you. "
    "I can't approve refunds myself."
)
_GREETING = re.compile(
    r"^\s*(?:hi+|hello|hey+|namaste|good\s+(?:morning|afternoon|evening))"
    r"(?:\s+(?:there|support|team|everyone))?\s*[.!?]*\s*$",
    re.I,
)


def clean_reply(text: str) -> str:
    """Drops a contradictory 'I don't have that detail.' opener when an answer follows."""
    t = (text or "").strip()
    t = re.sub(r"^(?:Sure|Certainly|Of course|Absolutely)[,!.]?\s+(?:here(?:'s| is)[^:.\n]*[:.]\s*)?", "", t, flags=re.I).strip()
    m = re.match(r"^I don't have that detail\.\s+(.{20,})$", t, re.S)
    if m and not re.search(r"\b(not mention|only mentions?|only mention)\b", m.group(1), re.I):
        return m.group(1).strip()
    return t

def is_greeting(text: str) -> bool:
    return bool(_GREETING.match(text or ""))


def build_prompt_with_context(user_message: str):
    start = time.time()
    chunks = retrieve(to_english_query(user_message), top_k=3)
    retrieval_time = time.time() - start
    best_distance = min((c["distance"] for c in chunks), default=float("inf"))
    context_text = "\n\n".join([f"[{c['source']}]\n{c['text']}" for c in chunks])
    prompt = f"Context:\n{context_text}\n\nCustomer question: {user_message}"
    return prompt, retrieval_time, best_distance


def handle_support(
    user_message: str,
    user: User | None = None,
    db: Session | None = None,
    source: str = "chat",
) -> str:
    if is_greeting(user_message):
        return greeting_for(user)

    sentiment, category = classify(user_message)
    escalate = should_escalate(sentiment, category)
    print(f"[CLASSIFY] sentiment={sentiment} category={category} escalate={escalate}")

    if escalate and db is not None:
        ticket = create_ticket(db, user, user_message, sentiment, category, source)
        print(f"[TICKET] opened #{ticket.id}")

    if escalate and category == "refund_request":
        return REFUND_REPLY

    prompt_with_context, retrieval_time, best_distance = build_prompt_with_context(user_message)

    if best_distance > MAX_DISTANCE:
        print(f"[RAG] best distance {best_distance:.3f} > {MAX_DISTANCE}, skipping LLM")
        reply = NO_ANSWER_REPLY
    else:
        llm = get_llm()
        gen_start = time.time()
        output = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *FEWSHOT,
                {"role": "user", "content": prompt_with_context},
            ],
            max_tokens=200,
            **SAMPLING,
        )
        print(f"[TIMING] Support | Retrieval: {retrieval_time:.3f}s | Generation: {time.time() - gen_start:.3f}s")
        reply = clean_reply(output["choices"][0]["message"]["content"])

    if escalate:
        reply += "\n\n(This has been flagged for priority review by our support team.)"

    return reply


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    intent = classify_intent(request.message)
    print(f"[INTENT] '{request.message}' -> {intent}")

    if intent == "order":
        reply_text = handle_order(request.message, user, db)
    else:
        reply_text = handle_support(request.message, user, db, "chat")

    return ChatResponse(reply=reply_text)


@router.post("/chat/stream")
def chat_stream(
    request: ChatRequest,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    intent = classify_intent(request.message)
    print(f"[INTENT] '{request.message}' -> {intent}")

    if intent == "order":
        order_reply = handle_order(request.message, user, db)

        def order_generator():
            yield f"data: {json.dumps({'token': order_reply})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(order_generator(), media_type="text/event-stream")

    if is_greeting(request.message):
        def greeting_generator():
            yield f"data: {json.dumps({'token': greeting_for(user)})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(greeting_generator(), media_type="text/event-stream")

    sentiment, category = classify(request.message)
    escalate = should_escalate(sentiment, category)
    print(f"[CLASSIFY] sentiment={sentiment} category={category} escalate={escalate}")

    # The ticket is created now, before streaming starts, while the DB session is still open.
    escalate_event = ""
    if escalate:
        ticket_id = create_ticket(db, user, request.message, sentiment, category, "chat").id
        print(f"[TICKET] opened #{ticket_id}")
        escalate_event = f"data: {json.dumps({'escalate': True, 'ticket_id': ticket_id})}\n\n"

    if escalate and category == "refund_request":
        def refund_generator():
            yield f"data: {json.dumps({'token': REFUND_REPLY})}\n\n"
            yield escalate_event
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(refund_generator(), media_type="text/event-stream")

    prompt_with_context, retrieval_time, best_distance = build_prompt_with_context(request.message)
    print(f"[TIMING] Retrieval: {retrieval_time:.3f}s")

    if best_distance > MAX_DISTANCE:
        print(f"[RAG] best distance {best_distance:.3f} > {MAX_DISTANCE}, skipping LLM")

        def no_answer_generator():
            yield f"data: {json.dumps({'token': NO_ANSWER_REPLY})}\n\n"
            if escalate_event:
                yield escalate_event
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(no_answer_generator(), media_type="text/event-stream")

    llm = get_llm()

    def token_generator():
        gen_start = time.time()
        first_token_time = None
        stream = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *FEWSHOT,
                {"role": "user", "content": prompt_with_context},
            ],
            max_tokens=200,
            **SAMPLING,
            stream=True,
        )
        for chunk in stream:
            delta = chunk["choices"][0]["delta"]
            token = delta.get("content", "")
            if token:
                if first_token_time is None:
                    first_token_time = time.time() - gen_start
                    print(f"[TIMING] First token: {first_token_time:.3f}s")
                yield f"data: {json.dumps({'token': token})}\n\n"
        print(f"[TIMING] Full generation: {time.time() - gen_start:.3f}s")
        if escalate_event:
            yield escalate_event
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(token_generator(), media_type="text/event-stream")


@router.post("/voice-chat", response_model=ChatResponse)
async def voice_chat(
    file: UploadFile = File(...),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    whisper = get_whisper()

    temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.wav")
    try:
        audio_bytes = await file.read()
        with open(temp_path, "wb") as f:
            f.write(audio_bytes)

        t_start = time.time()
        segments = whisper.transcribe(temp_path, language="en")
        transcribed_text = " ".join([s.text for s in segments]).strip()
        print(f"[TIMING] Transcription: {time.time() - t_start:.3f}s")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    intent = classify_intent(transcribed_text)
    print(f"[INTENT] '{transcribed_text}' -> {intent}")

    if intent == "order":
        reply_text = handle_order(transcribed_text, user, db)
    else:
        reply_text = handle_support(transcribed_text, user, db, "voice")

    return ChatResponse(reply=reply_text)
