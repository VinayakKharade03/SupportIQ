import re

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.ml.product_search import search_products
from app.routers.orders import CartAdd, add_to_cart, confirm_order, view_cart
from app.services import order_chat
from app.services.security import decode_access_token

MIN_SCORE = 0.4  # cosine similarity: higher = closer. Real matches >= 0.55, unrelated <= 0.3
LOGIN_REPLY = "Please log in first so I can manage your cart and orders."

optional_bearer = HTTPBearer(auto_error=False)

PRICE_LIMIT = re.compile(r"(?:under|below|less than|within|upto|up to)\s*(?:rs\.?)?\s*(\d[\d,]*)")
QUANTITY = re.compile(r"(?<![\d.])(\d{1,2})(?!\d|\.\d)")
FILLER = re.compile(
    r"\b(?:add|put|to|in|my|cart|buy|purchase|order|i|want|get|need|the|a|an|some|pair|"
    r"please|checkout|looking|for|me|how|much|is|price|of|cost|cheap|cheapest)\b"
)
ADD_WORDS = ("add", "put", "buy", "purchase", "order", "get", "want", "need")


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    """Returns the logged-in user, or None if there is no valid token."""
    if creds is None:
        return None
    try:
        user_id = int(decode_access_token(creds.credentials)["sub"])
    except (JWTError, KeyError, ValueError):
        return None
    return db.get(User, user_id)


def _format_cart(cart: dict) -> str:
    if not cart["items"]:
        return "Your cart is empty."
    lines = [f"- {i['quantity']} x {i['name']} (Rs {i['line_total']:.0f})" for i in cart["items"]]
    return "Your cart:\n" + "\n".join(lines) + f"\nTotal: Rs {cart['total']:.0f}"


def _find_products(text: str):
    """Returns (matching products, quantity, wants_cheapest) for a message."""
    without_price = PRICE_LIMIT.sub(" ", text)
    limit_match = PRICE_LIMIT.search(text)
    price_limit = float(limit_match.group(1).replace(",", "")) if limit_match else None

    qty_match = QUANTITY.search(without_price)
    quantity = max(1, int(qty_match.group(1))) if qty_match else 1

    query = QUANTITY.sub(" ", without_price)
    query = FILLER.sub(" ", query)
    query = re.sub(r"[^\w\s.\-]", " ", query)
    query = " ".join(query.split())
    if not query:
        return [], quantity, False

    wants_cheapest = "cheap" in text
    results = [r for r in search_products(query, top_k=5) if r["score"] >= MIN_SCORE]
    if price_limit is not None:
        results = [r for r in results if r["price"] <= price_limit]
    if wants_cheapest:
        results.sort(key=lambda r: r["price"])
    return results, quantity, wants_cheapest


def handle_order(message: str, user: User | None = None, db: Session | None = None) -> str:
    text = message.lower()
    needs_login = user is None or db is None

    # 0. Order management: remove from cart, order status, cancel (confirm-before-cancel)
    managed = order_chat.handle(text, user, db, LOGIN_REPLY)
    if managed is not None:
        return managed

    # 1. Confirm: the only step that actually places the order
    if "confirm" in text or "place order" in text or "place my order" in text:
        print("[ORDER] action=confirm")
        if needs_login:
            return LOGIN_REPLY
        try:
            result = confirm_order(user=user, db=db)
        except HTTPException as e:
            return str(e.detail)
        return f"Your order #{result['order_id']} is confirmed. Total: Rs {result['total']:.0f}."

    # 2. Show cart
    if ("cart" in text and not any(w in text for w in ("add", "put"))) or "checkout" in text:
        print("[ORDER] action=view_cart")
        if needs_login:
            return LOGIN_REPLY
        cart = view_cart(user=user, db=db)
        reply = _format_cart(cart)
        if cart["items"]:
            reply += "\nSay 'confirm order' to place it."
        return reply

    # 3. Product search: browse or add
    products, quantity, _ = _find_products(text)
    wants_to_add = any(w in text for w in ADD_WORDS)
    print(f"[ORDER] action={'add' if wants_to_add else 'browse'} matches={[p['name'] for p in products]}")

    if not products:
        return "I couldn't find a matching product. Could you tell me what kind of product you're looking for, like earbuds, a speaker, or a soundbar?"

    if not wants_to_add:
        lines = [f"- {p['name']}: Rs {p['price']:.0f}" for p in products[:3]]
        return "Here's what I found:\n" + "\n".join(lines) + "\nTell me which one you'd like and I'll add it to your cart."

    if needs_login:
        return LOGIN_REPLY
    product = products[0]
    try:
        cart = add_to_cart(CartAdd(product_id=product["id"], quantity=quantity), user=user, db=db)
    except HTTPException as e:
        return str(e.detail)
    return (
        f"Added {quantity} x {product['name']} to your cart. Cart total: Rs {cart['total']:.0f}.\n"
        "Say 'confirm order' to place it, or keep shopping."
    )

