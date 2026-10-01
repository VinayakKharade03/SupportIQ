import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.routers import auth, support, orders, voice


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=voice.warm_up, daemon=True).start()
    yield


app = FastAPI(title="SupportIQ", lifespan=lifespan)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(support.router, prefix="/support", tags=["support"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])
app.include_router(voice.router, prefix="/voice", tags=["voice"])


@app.get("/health")
def health():
    return {"status": "ok"}
