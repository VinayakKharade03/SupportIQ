import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.routers.my_orders import cancel_my_order, get_my_order, list_my_orders
from app.routers.orders import CartRemove, remove_from_cart, view_cart

CANCEL = re.compile(r"\bcancel\b")
ORDER_WORD = re.compile(r"\borders?\b")
ORDER_NUMBER = re.compile(r"\border\s*(?:no\.?|number|id)?\s*#?\s*(\d{1,9})\b|#\s*(\d{1,9})\b")
CONFIRM_WORDS = re.compile(r"\b(?:yes|yep|yeah|sure|confirm|proceed|go ahead)\b")
NEGATION = re.compile(r"\b(?:don't|dont|do not|not|never|wait|stop)\b")

CART_WORD = re.compile(r"\b(?:cart|basket)\b")
REMOVE_VERBS = re.compile(r"\b(?:remove|delete|take out|take off|get rid of|drop|clear)\b")
CLEAR_CART = re.compile(r"\b(?:clear|empty)\s+(?:out\s+)?(?:(?:my|the|whole|entire)\s+)*(?:cart|basket)\b")
REMOVE_ALL = re.compile(
    r"\b(?:remove|delete)\s+(?:everything|all(?:\s+(?:the\s+)?items)?)\s+(?:from|in)\s+(?:(?:my|the)\s+)?(?:cart|basket)\b"
)
ADD_WORDS = re.compile(r"\b(?:add|put|buy|purchase)\b")

STATUS_PATTERNS = [
    re.compile(r"\bwhere(?:'s| is| are)\s+my\s+(?:orders?|packages?|parcels?|deliver(?:y|ies)|shipments?)\b"),
    re.compile(r"\bwhen\s+(?:will|does|is)\s+my\s+(?:orders?|packages?|parcels?|deliver(?:y|ies)|shipments?)\b"),
    re.compile(r"\b(?:track|tracking|status)\b.{0,30}\b(?:orders?|packages?|parcels?|shipments?|deliver(?:y|ies))\b"),
    re.compile(r"\borders?\s+(?:status|tracking|history)\b"),
    re.compile(r"\b(?:my|past|previous|recent|latest|last)\s+orders\b"),
    re.compile(r"\bwhat did i (?:order|buy)\b"),
]
NOT_STATUS = re.compile(r"\b(?:confirm|place|add|buy|purchase)\b")

STOP = {
    "remove", "delete", "take", "out", "off", "get", "rid", "of", "drop", "clear",
    "the", "a", "an", "my", "from", "in", "cart", "basket", "please", "it", "that",
    "this", "one", "item", "can", "you", "could", "i", "would", "like", "want", "to",
    "and", "just",
}


def _tokens(text):
    words = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if w.isdigit():
            continue
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        words.add(w)
    return words


def _order_number(text):
    m = ORDER_NUMBER.search(text)
    if not m:
        return None
    return int(m.group(1) or m.group(2))


def _names(items):
    return ", ".join(i["name"] for i in items)


def _remove_item(item, user, db):
    try:
        cart = remove_from_cart(CartRemove(product_id=item["product_id"]), user=user, db=db)
    except HTTPException as e:
        return str(e.detail)
    if not cart["items"]:
        return f"Removed {item['name']} from your cart. Your cart is now empty."
    return f"Removed {item['name']} from your cart. Cart total: Rs {cart['total']:.0f}."


def _remove(text, user, db):
    items = view_cart(user=user, db=db)["items"]
    if not items:
        return "Your cart is empty."

    if CLEAR_CART.search(text) or REMOVE_ALL.search(text):
        for item in items:
            try:
                remove_from_cart(CartRemove(product_id=item["product_id"]), user=user, db=db)
            except HTTPException as e:
                return str(e.detail)
        return "I've emptied your cart."

    wanted = _tokens(text) - STOP
    if not wanted:
        if len(items) == 1:
            return _remove_item(items[0], user, db)
        return f"Which item should I remove? Your cart has: {_names(items)}."

    scored = [(len(wanted & _tokens(i["name"])), i) for i in items]
    best = max(score for score, _ in scored)
    if best == 0:
        return f"I couldn't find that in your cart. Your cart has: {_names(items)}."
    matches = [i for score, i in scored if score == best]
    if len(matches) > 1:
        return f"Which one do you mean? {_names(matches)}."
    return _remove_item(matches[0], user, db)


def _status(text, user, db):
    number = _order_number(text)
    if number is not None:
        try:
            order = get_my_order(order_id=number, user=user, db=db)
        except HTTPException:
            return f"I couldn't find order #{number} on your account."
        items = ", ".join(f"{i.quantity} x {i.name}" for i in order.items)
        return f"Order #{order.id} is {order.status}: {items}. Total: Rs {order.total:.0f}."

    orders = list_my_orders(status=None, limit=3, offset=0, user=user, db=db)
    if not orders:
        return "You haven't placed any orders yet."
    lines = [f"- Order #{o.id}: {o.status}, {o.units} item(s), Rs {o.total:.0f}" for o in orders]
    return (
        "Your recent orders:\n" + "\n".join(lines)
        + f"\nAsk about one, for example 'status of order {orders[0].id}'."
    )


def _cancel(text, user, db):
    number = _order_number(text)
    confirmed = bool(CONFIRM_WORDS.search(text)) and not NEGATION.search(text)

    if number is None:
        orders = list_my_orders(status="confirmed", limit=5, offset=0, user=user, db=db)
        if not orders:
            return "You don't have any orders that can be cancelled."
        if len(orders) == 1:
            o = orders[0]
            return (
                f"Your order #{o.id} ({o.units} item(s), Rs {o.total:.0f}) can be cancelled. "
                f"Say 'yes, cancel order {o.id}' to confirm."
            )
        lines = [f"- Order #{o.id}: {o.units} item(s), Rs {o.total:.0f}" for o in orders]
        return "These orders can be cancelled:\n" + "\n".join(lines) + "\nTell me which one, for example 'cancel order N'."

    try:
        order = get_my_order(order_id=number, user=user, db=db)
    except HTTPException:
        return f"I couldn't find order #{number} on your account."
    if order.status == "cancelled":
        return f"Order #{number} is already cancelled."
    if order.status != "confirmed":
        return f"Order #{number} is {order.status}, so it can't be cancelled."

    if not confirmed:
        items = ", ".join(f"{i.quantity} x {i.name}" for i in order.items)
        return (
            f"Order #{number} ({items}, Rs {order.total:.0f}) can be cancelled. "
            f"Say 'yes, cancel order {number}' to confirm."
        )
    try:
        cancel_my_order(order_id=number, user=user, db=db)
    except HTTPException as e:
        return str(e.detail)
    return f"Order #{number} has been cancelled."


def handle(text: str, user: User | None, db: Session | None, login_reply: str):
    """Order management by chat or voice: cancel, remove from cart, order status.
    Returns a reply, or None if the message is not one of these (so normal ordering continues)."""
    text = text.replace("\u2019", "'")  # speech-to-text can produce a curly apostrophe

    if CANCEL.search(text) and ORDER_WORD.search(text):
        handler = _cancel
    elif CART_WORD.search(text) and (REMOVE_VERBS.search(text) or CLEAR_CART.search(text)):
        if ADD_WORDS.search(text):
            return "Let's do one thing at a time: tell me either what to remove or what to add."
        handler = _remove
    elif any(p.search(text) for p in STATUS_PATTERNS) and not NOT_STATUS.search(text):
        handler = _status
    else:
        return None

    if user is None or db is None:
        return login_reply
    return handler(text, user, db)
