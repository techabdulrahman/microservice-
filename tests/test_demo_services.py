import importlib.util
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]


def load_app(name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


product_service = load_app(
    "demo_product_service",
    ROOT / "services" / "product-service" / "app" / "main.py",
)
order_service = load_app(
    "demo_order_service",
    ROOT / "services" / "order-service" / "app" / "main.py",
)
api_gateway = load_app(
    "demo_api_gateway",
    ROOT / "api-gateway" / "app" / "main.py",
)


@pytest.fixture(autouse=True)
def clear_demo_orders():
    order_service.orders.clear()
    order_service.idempotent_orders.clear()
    yield
    order_service.orders.clear()
    order_service.idempotent_orders.clear()


def test_product_catalog_and_filter():
    client = TestClient(product_service.app)
    response = client.get("/products")
    assert response.status_code == 200
    assert len(response.json()) == 6
    assert client.get("/products?category=home").json()[0]["id"] == "mug"
    assert client.get("/products/not-a-product").status_code == 404


def test_order_uses_catalog_price_and_idempotency(monkeypatch):
    async def fake_fetch_product(_client, product_id):
        if product_id != "mug":
            raise HTTPException(status_code=422, detail="Unknown product")
        return {"id": "mug", "name": "Sunday Studio Mug", "price_cents": 2400}

    monkeypatch.setattr(order_service, "fetch_product", fake_fetch_product)
    client = TestClient(order_service.app)
    payload = {
        "customer_name": "Alex",
        "items": [{"product_id": "mug", "quantity": 2}],
    }
    first = client.post("/orders", json=payload, headers={"Idempotency-Key": "demo-order-1"})
    second = client.post("/orders", json=payload, headers={"Idempotency-Key": "demo-order-1"})
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    assert first.json()["total_cents"] == 4800
    assert len(client.get("/orders").json()) == 1


def test_order_rejects_invalid_quantity():
    client = TestClient(order_service.app)
    response = client.post(
        "/orders",
        json={"customer_name": "Alex", "items": [{"product_id": "mug", "quantity": 0}]},
    )
    assert response.status_code == 422


def test_gateway_routes_products_and_forwards_order_key(monkeypatch):
    calls = []

    async def fake_forward(url, method="GET", **kwargs):
        calls.append((url, method, kwargs))
        from fastapi import Response

        return Response(content="[]", media_type="application/json")

    monkeypatch.setattr(api_gateway, "forward", fake_forward)
    client = TestClient(api_gateway.app)
    assert client.get("/api/products").json() == []
    assert client.get("/api/products?category=Home").json() == []
    assert client.post(
        "/api/orders",
        json={"customer_name": "Alex", "items": [{"product_id": "mug", "quantity": 1}]},
        headers={"Idempotency-Key": "gateway-test"},
    ).status_code == 200
    assert calls[0][0].endswith("/products")
    assert calls[0][2]["params"] is None
    assert calls[1][2]["params"] == {"category": "Home"}
    assert calls[2][1] == "POST"
    assert calls[2][2]["headers"] == {"Idempotency-Key": "gateway-test"}
