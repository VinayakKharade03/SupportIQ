from fastapi import FastAPI
from app.routers import auth, support, orders

app = FastAPI(title="SupportIQ")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(support.router, prefix="/support", tags=["support"])
app.include_router(orders.router, prefix="/orders", tags=["orders"])


@app.get("/health")
def health():
    return {"status": "ok"}