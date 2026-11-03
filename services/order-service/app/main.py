import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator

PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8001")

app = FastAPI(title="Colorful Market - Order Service", version="1.0.0")
orders: list[dict] = []
idempotent_orders: dict[str, dict] = {}
orders_lock = asyncio.Lock()


class OrderItemRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=40)
    quantity: int = Field(ge=1, le=10)


class OrderRequest(BaseModel):
    customer_name: str = Field(min_length=1, max_length=80)
    items: list[OrderItemRequest] = Field(min_length=1, max_length=20)

    @field_validator("customer_name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name must not be blank")
        return value


async def fetch_product(client: httpx.AsyncClient, product_id: str) -> dict:
    response = await client.get(f"{PRODUCT_SERVICE_URL}/products/{product_id}")
    if response.status_code == 404:
        raise HTTPException(status_code=422, detail=f"Unknown product: {product_id}")
    response.raise_for_status()
    return response.json()


@app.get("/healthz")
async def health():
    return {"status": "ok"}


@app.get("/readyz")
async def ready():
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{PRODUCT_SERVICE_URL}/readyz")
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="Product service is unavailable") from error
    return {"status": "ready"}


@app.get("/orders")
async def list_orders():
    async with orders_lock:
        return list(reversed(orders))


@app.post("/orders", status_code=status.HTTP_201_CREATED)
async def create_order(
    request: OrderRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
):
    async with orders_lock:
        if idempotency_key and idempotency_key in idempotent_orders:
            return idempotent_orders[idempotency_key]

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            items = []
            total_cents = 0
            for requested_item in request.items:
                product = await fetch_product(client, requested_item.product_id)
                line_total = product["price_cents"] * requested_item.quantity
                total_cents += line_total
                items.append(
                    {
                        "product_id": product["id"],
                        "name": product["name"],
                        "quantity": requested_item.quantity,
                        "unit_price_cents": product["price_cents"],
                        "line_total_cents": line_total,
                    }
                )
    except httpx.HTTPStatusError as error:
        raise HTTPException(status_code=503, detail="Product service returned an error") from error
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="Product service is unavailable") from error

    order = {
        "id": str(uuid4())[:8],
        "customer_name": request.customer_name.strip(),
        "items": items,
        "total_cents": total_cents,
        "status": "confirmed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    async with orders_lock:
        if idempotency_key and idempotency_key in idempotent_orders:
            return idempotent_orders[idempotency_key]
        orders.append(order)
        if idempotency_key:
            idempotent_orders[idempotency_key] = order
    return order
