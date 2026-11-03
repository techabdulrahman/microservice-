const state = { products: [], cart: new Map(), category: "All" };
const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const grid = document.querySelector("#product-grid");
const categoryRow = document.querySelector("#categories");
const cartDrawer = document.querySelector("#cart-drawer");
const backdrop = document.querySelector("#cart-backdrop");
let toastTimer;

function showToast(message) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("visible"), 2400);
}

async function api(path, options) {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Something went wrong. Please try again.");
  }
  return response.json();
}

function renderCategories() {
  const categories = ["All", ...new Set(state.products.map((product) => product.category))];
  categoryRow.replaceChildren();
  categories.forEach((category) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `category-chip${state.category === category ? " active" : ""}`;
    button.textContent = category;
    button.addEventListener("click", () => {
      state.category = category;
      renderCategories();
      renderProducts();
    });
    categoryRow.append(button);
  });
}

function renderProducts() {
  const products = state.category === "All"
    ? state.products
    : state.products.filter((product) => product.category === state.category);
  grid.replaceChildren();
  if (products.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-products";
    empty.textContent = "No little finds in this category just yet.";
    grid.append(empty);
    return;
  }

  products.forEach((product) => {
    const card = document.createElement("article");
    card.className = "product-card";
    const art = document.createElement("div");
    art.className = "product-art";
    art.style.setProperty("--card-color", product.color);
    const badge = document.createElement("span");
    badge.className = "product-badge";
    badge.textContent = product.badge;
    const image = document.createElement("img");
    image.src = product.image_url;
    image.alt = product.name;
    image.loading = "lazy";
    const add = document.createElement("button");
    add.className = "product-add";
    add.type = "button";
    add.textContent = "+";
    add.setAttribute("aria-label", `Add ${product.name} to bag`);
    add.addEventListener("click", () => changeQuantity(product.id, 1));
    art.append(badge, image, add);

    const info = document.createElement("div");
    info.className = "product-info";
    const description = document.createElement("div");
    const name = document.createElement("h3");
    name.textContent = product.name;
    const detail = document.createElement("p");
    detail.textContent = product.description;
    description.append(name, detail);
    const price = document.createElement("span");
    price.className = "product-price";
    price.textContent = currency.format(product.price_cents / 100);
    info.append(description, price);
    card.append(art, info);
    grid.append(card);
  });
}

function changeQuantity(productId, delta) {
  const quantity = (state.cart.get(productId) || 0) + delta;
  if (quantity <= 0) state.cart.delete(productId);
  else state.cart.set(productId, Math.min(quantity, 10));
  renderCart();
  if (delta > 0) showToast("A little joy added to your bag ✳");
}

function renderCart() {
  const items = [...state.cart.entries()];
  const count = items.reduce((sum, [, quantity]) => sum + quantity, 0);
  document.querySelector("#cart-count").textContent = count;
  document.querySelector("#drawer-count").textContent = `(${count})`;
  const cartItems = document.querySelector("#cart-items");
  cartItems.replaceChildren();
  let total = 0;
  if (items.length === 0) {
    const empty = document.createElement("p");
    empty.className = "cart-empty";
    empty.textContent = "Your bag is taking a little breather. Find a favorite and bring it along.";
    cartItems.append(empty);
  }
  items.forEach(([productId, quantity]) => {
    const product = state.products.find((candidate) => candidate.id === productId);
    if (!product) return;
    total += product.price_cents * quantity;
    const row = document.createElement("div");
    row.className = "cart-line";
    const image = document.createElement("img");
    image.src = product.image_url;
    image.alt = "";
    image.style.setProperty("--card-color", product.color);
    const detail = document.createElement("div");
    const name = document.createElement("h3");
    name.textContent = product.name;
    const price = document.createElement("p");
    price.textContent = currency.format(product.price_cents / 100);
    const control = document.createElement("div");
    control.className = "quantity-control";
    const minus = document.createElement("button");
    minus.type = "button";
    minus.textContent = "−";
    minus.setAttribute("aria-label", `Remove one ${product.name}`);
    minus.addEventListener("click", () => changeQuantity(productId, -1));
    const quantityText = document.createElement("span");
    quantityText.textContent = quantity;
    const plus = document.createElement("button");
    plus.type = "button";
    plus.textContent = "+";
    plus.setAttribute("aria-label", `Add one ${product.name}`);
    plus.addEventListener("click", () => changeQuantity(productId, 1));
    control.append(minus, quantityText, plus);
    detail.append(name, price, control);
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "cart-remove";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      state.cart.delete(productId);
      renderCart();
    });
    row.append(image, detail, remove);
    cartItems.append(row);
  });
  document.querySelector("#cart-total").textContent = currency.format(total / 100);
}

function setCartOpen(open) {
  cartDrawer.classList.toggle("open", open);
  cartDrawer.setAttribute("aria-hidden", String(!open));
  backdrop.hidden = !open;
  document.body.style.overflow = open ? "hidden" : "";
  if (open) document.querySelector("#customer-name").focus();
}

async function checkout() {
  const items = [...state.cart.entries()].map(([product_id, quantity]) => ({ product_id, quantity }));
  const customerName = document.querySelector("#customer-name").value.trim();
  if (!items.length) return showToast("Your bag is empty—find a little favorite first.");
  if (!customerName) {
    document.querySelector("#customer-name").focus();
    return showToast("Add your first name to place a demo order.");
  }

  const button = document.querySelector("#checkout-button");
  button.disabled = true;
  button.textContent = "Making a little magic…";
  try {
    const order = await api("/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify({ customer_name: customerName, items }),
    });
    state.cart.clear();
    document.querySelector("#customer-name").value = "";
    renderCart();
    setCartOpen(false);
    showToast(`Order #${order.id} is in! Thanks, ${order.customer_name} ✳`);
  } catch (error) {
    showToast(error.message);
  } finally {
    button.disabled = false;
    button.innerHTML = 'Place demo order <span aria-hidden="true">↗</span>';
  }
}

async function start() {
  try {
    state.products = await api("/products");
    renderCategories();
    renderProducts();
    renderCart();
  } catch (error) {
    grid.replaceChildren();
    const message = document.createElement("p");
    message.className = "empty-products";
    message.textContent = `The shop is taking a tiny break. ${error.message}`;
    grid.append(message);
  }
}

document.querySelector("#cart-open").addEventListener("click", () => setCartOpen(true));
document.querySelector("#cart-close").addEventListener("click", () => setCartOpen(false));
backdrop.addEventListener("click", () => setCartOpen(false));
document.querySelector("#checkout-button").addEventListener("click", checkout);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setCartOpen(false);
});
start();
