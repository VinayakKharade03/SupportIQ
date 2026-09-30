import os
import time
import tempfile
import uuid
import json

from fastapi import APIRouter, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse
from app.ml.model_loader import get_llm, get_whisper
from app.ml.rag import retrieve
from app.ml.intent_router import classify_intent
from app.ml.classifiers import classify
from app.services.order_agent import handle_order, get_optional_user

router = APIRouter()

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


def build_prompt_with_context(user_message: str):
    start = time.time()
    chunks = retrieve(user_message, top_k=3)
    retrieval_time = time.time() - start
    best_distance = min((c["distance"] for c in chunks), default=float("inf"))
    context_text = "\n\n".join([f"[{c['source']}]\n{c['text']}" for c in chunks])
    prompt = f"Context:\n{context_text}\n\nCustomer question: {user_message}"
    return prompt, retrieval_time, best_distance


def handle_support(user_message: str) -> str:
    sentiment, category = classify(user_message)
    escalate = sentiment == "negative" and category in ("recurring_issue", "refund_request")
    print(f"[CLASSIFY] sentiment={sentiment} category={category} escalate={escalate}")

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
                {"role": "user", "content": prompt_with_context},
            ],
            max_tokens=200,
        )
        print(f"[TIMING] Support | Retrieval: {retrieval_time:.3f}s | Generation: {time.time() - gen_start:.3f}s")
        reply = output["choices"][0]["message"]["content"]

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
        reply_text = handle_support(request.message)

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

    sentiment, category = classify(request.message)
    print(f"[CLASSIFY] sentiment={sentiment} category={category}")

    prompt_with_context, retrieval_time, best_distance = build_prompt_with_context(request.message)
    print(f"[TIMING] Retrieval: {retrieval_time:.3f}s")

    if best_distance > MAX_DISTANCE:
        print(f"[RAG] best distance {best_distance:.3f} > {MAX_DISTANCE}, skipping LLM")

        def no_answer_generator():
            yield f"data: {json.dumps({'token': NO_ANSWER_REPLY})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(no_answer_generator(), media_type="text/event-stream")

    llm = get_llm()

    def token_generator():
        gen_start = time.time()
        first_token_time = None
        stream = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_with_context},
            ],
            max_tokens=200,
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
        reply_text = handle_support(transcribed_text)

    return ChatResponse(reply=reply_text)
