import asyncio
import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, Response

PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8001")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8002")

app = FastAPI(title="Colorful Market - API Gateway", version="1.0.0")


async def forward(
    url: str,
    method: str = "GET",
    *,
    params: dict[str, Any] | None = None,
    body: Any = None,
    headers: dict[str, str] | None = None,
) -> Response:
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            upstream = await client.request(
                method,
                url,
                params=params,
                json=body,
                headers=headers,
            )
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="A required service is unavailable") from error
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers={"content-type": upstream.headers.get("content-type", "application/json")},
    )


@app.get("/healthz")
async def health():
    return {"status": "ok"}


@app.get("/readyz")
async def ready():
    checks = [
        f"{PRODUCT_SERVICE_URL}/readyz",
        f"{ORDER_SERVICE_URL}/readyz",
    ]
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            responses = await asyncio.gather(*(client.get(url) for url in checks))
        for response in responses:
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail="A required service is unavailable") from error
    return {"status": "ready"}


@app.get("/api/products")
async def list_products(category: str | None = None):
    params = {"category": category} if category is not None else None
    return await forward(f"{PRODUCT_SERVICE_URL}/products", params=params)


@app.get("/api/products/{product_id}")
async def get_product(product_id: str):
    return await forward(f"{PRODUCT_SERVICE_URL}/products/{product_id}")


@app.get("/api/orders")
async def list_orders():
    return await forward(f"{ORDER_SERVICE_URL}/orders")


@app.post("/api/orders")
async def create_order(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=100),
):
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON") from error
    headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
    return await forward(
        f"{ORDER_SERVICE_URL}/orders",
        "POST",
        body=body,
        headers=headers,
    )
