import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import (
    auth,
    support,
    orders,
    voice,
    products,
    admin_tickets,
    admin_users,
    admin_products,
    admin_orders,
    admin_stats,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=voice.warm_up, daemon=True).start()
    yield


app = FastAPI(title="SupportIQ", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(support.router, prefix="/support", tags=["support"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])
app.include_router(voice.router, prefix="/voice", tags=["voice"])
app.include_router(products.router, prefix="/products", tags=["products"])
app.include_router(admin_tickets.router, prefix="/admin/tickets", tags=["admin"])
app.include_router(admin_users.router, prefix="/admin/users", tags=["admin"])
app.include_router(admin_products.router, prefix="/admin/products", tags=["admin"])
app.include_router(admin_orders.router, prefix="/admin/orders", tags=["admin"])
app.include_router(admin_stats.router, prefix="/admin/stats", tags=["admin"])


@app.get("/health")
def health():
    return {"status": "ok"}
