import os
import time
import tempfile
import uuid
import json

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse
from app.ml.model_loader import get_llm, get_whisper
from app.ml.rag import retrieve
from app.ml.intent_router import classify_intent

router = APIRouter()

SYSTEM_PROMPT = (
    "You are a helpful customer support assistant for an audio electronics brand. "
    "Use the provided context to answer accurately. If the context doesn't cover "
    "the question, say so honestly rather than guessing."
)


def build_prompt_with_context(user_message: str):
    start = time.time()
    chunks = retrieve(user_message, top_k=3)
    retrieval_time = time.time() - start
    context_text = "\n\n".join([f"[{c['source']}]\n{c['text']}" for c in chunks])
    prompt = f"Context:\n{context_text}\n\nCustomer question: {user_message}"
    return prompt, retrieval_time


def handle_support(user_message: str) -> str:
    llm = get_llm()
    prompt_with_context, retrieval_time = build_prompt_with_context(user_message)

    gen_start = time.time()
    output = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_with_context},
        ],
        max_tokens=200,
    )
    print(f"[TIMING] Support | Retrieval: {retrieval_time:.3f}s | Generation: {time.time() - gen_start:.3f}s")
    return output["choices"][0]["message"]["content"]


def handle_order(user_message: str) -> str:
    # Placeholder until the product catalog + order logic is built.
    print("[INTENT] order path hit (placeholder)")
    return (
        "I can help you order that. Product catalog and ordering aren't fully "
        "wired up yet — this is a placeholder response confirming the order "
        "path was correctly routed."
    )


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    intent = classify_intent(request.message)
    print(f"[INTENT] '{request.message}' -> {intent}")

    if intent == "order":
        reply_text = handle_order(request.message)
    else:
        reply_text = handle_support(request.message)

    return ChatResponse(reply=reply_text)


@router.post("/chat/stream")
def chat_stream(request: ChatRequest):
    intent = classify_intent(request.message)
    print(f"[INTENT] '{request.message}' -> {intent}")

    if intent == "order":
        def order_generator():
            reply = handle_order(request.message)
            yield f"data: {json.dumps({'token': reply})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        return StreamingResponse(order_generator(), media_type="text/event-stream")

    llm = get_llm()
    prompt_with_context, retrieval_time = build_prompt_with_context(request.message)
    print(f"[TIMING] Retrieval: {retrieval_time:.3f}s")

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
async def voice_chat(file: UploadFile = File(...)):
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
        reply_text = handle_order(transcribed_text)
    else:
        reply_text = handle_support(transcribed_text)

    return ChatResponse(reply=reply_text)
