"""Tiny storefront API. Run: uvicorn main:app --app-dir demo-shopkart/api --port 8010"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from checkout import compute_total

app = FastAPI(title="Shopkart")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:5184",
        "http://localhost:5184",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Item(BaseModel):
    sku: str
    price: float
    qty: int = Field(ge=1, le=20)


class Checkout(BaseModel):
    items: list[Item]
    discount: float = 0


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/checkout")
def checkout(body: Checkout) -> dict:
    total = compute_total([item.model_dump() for item in body.items], body.discount)
    return {"total": total, "currency": "INR"}


@app.exception_handler(ZeroDivisionError)
async def coupon_crash(request: Request, exc: ZeroDivisionError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": "ZeroDivisionError", "detail": "division by zero"})
