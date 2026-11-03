from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="Colorful Market - Product Service", version="1.0.0")

PRODUCTS = [
    {
        "id": "mug",
        "name": "Sunday Studio Mug",
        "category": "Home",
        "description": "A cheerful ceramic mug for slow mornings.",
        "price_cents": 2400,
        "color": "#f8b4c8",
        "image_url": "/images/mug.svg",
        "badge": "Bestseller",
    },
    {
        "id": "lamp",
        "name": "Little Sun Lamp",
        "category": "Home",
        "description": "A warm glow and a little pop of color.",
        "price_cents": 6800,
        "color": "#ffd978",
        "image_url": "/images/lamp.svg",
        "badge": "New",
    },
    {
        "id": "plant",
        "name": "Pocket Jungle Plant",
        "category": "Living",
        "description": "A low-fuss leafy friend for your favorite shelf.",
        "price_cents": 3200,
        "color": "#bce6c8",
        "image_url": "/images/plant.svg",
        "badge": "Easy care",
    },
    {
        "id": "headphones",
        "name": "Daydream Headphones",
        "category": "Tech",
        "description": "Soft colors for your next big playlist.",
        "price_cents": 8900,
        "color": "#c8bbff",
        "image_url": "/images/headphones.svg",
        "badge": "Fan favorite",
    },
    {
        "id": "backpack",
        "name": "Weekend Mini Pack",
        "category": "Everyday",
        "description": "A bright little bag for wherever the day goes.",
        "price_cents": 5400,
        "color": "#ffc895",
        "image_url": "/images/backpack.svg",
        "badge": "Limited color",
    },
    {
        "id": "bottle",
        "name": "Good Day Bottle",
        "category": "Everyday",
        "description": "A reusable bottle that brings its own sunshine.",
        "price_cents": 2800,
        "color": "#a9dff0",
        "image_url": "/images/bottle.svg",
        "badge": "Feel-good pick",
    },
]


@app.get("/healthz")
async def health():
    return {"status": "ok"}


@app.get("/readyz")
async def ready():
    return {"status": "ready"}


@app.get("/products")
async def list_products(category: str | None = Query(default=None)):
    if category is None or category.lower() == "all":
        return PRODUCTS
    return [product for product in PRODUCTS if product["category"].lower() == category.lower()]


@app.get("/products/{product_id}")
async def get_product(product_id: str):
    for product in PRODUCTS:
        if product["id"] == product_id:
            return product
    raise HTTPException(status_code=404, detail="Product not found")
