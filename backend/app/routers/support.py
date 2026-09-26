from fastapi import APIRouter
from app.schemas.chat import ChatRequest, ChatResponse
from app.ml.model_loader import get_llm

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    llm = get_llm()

    output = llm.create_chat_completion(
        messages=[
            {
                "role": "system",
                "content": "You are a helpful customer support assistant for an audio electronics brand.",
            },
            {"role": "user", "content": request.message},
        ],
        max_tokens=200,
    )

    reply_text = output["choices"][0]["message"]["content"]
    return ChatResponse(reply=reply_text)
