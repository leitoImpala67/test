import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

SOURCE_URL = os.getenv("SOURCE_URL", "https://test.ooobs.ru/api/orders")
app = FastAPI(title="Order Sync", docs_url=None, redoc_url=None)


def normalize_phone(value: Any) -> str | None:
    if value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    # Russian numbers are commonly entered as 10 digits, 8XXXXXXXXXX, or 7XXXXXXXXXX.
    if len(digits) == 10:
        digits = "7" + digits
    elif len(digits) == 11 and digits[0] == "8":
        digits = "7" + digits[1:]
    elif len(digits) == 11 and digits[0] == "7":
        pass
    else:
        return None
    if len(digits) != 11 or digits[0] != "7":
        return None
    return "+" + digits


def parse_date(value: Any) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def parse_amount(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("-Infinity")


async def synchronize() -> dict:
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            response = await client.get(SOURCE_URL, headers={"Accept": "application/json"})
            response.raise_for_status()
            orders = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Could not retrieve valid orders from source API") from exc

    if not isinstance(orders, list):
        raise HTTPException(status_code=502, detail="Source API response must be a JSON array")

    winners: dict[str, tuple[Decimal, datetime, dict]] = {}
    invalid_dropped = 0
    valid_count = 0

    for order in orders:
        if not isinstance(order, dict):
            invalid_dropped += 1
            continue
        phone = normalize_phone(order.get("phone"))
        if phone is None:
            invalid_dropped += 1
            continue
        valid_count += 1
        amount = parse_amount(order.get("amount"))
        created = parse_date(order.get("created_at"))
        client = {
            "name": order.get("name") if order.get("name") is not None else "",
            "phone": phone,
            "email": order.get("email") if order.get("email") is not None else "",
            "amount": order.get("amount"),
        }
        current = winners.get(phone)
        if current is None or (amount, created) > (current[0], current[1]):
            winners[phone] = (amount, created, client)

    clients = [entry[2] for _, entry in sorted(winners.items(), key=lambda item: item[0])]
    return {
        "clients": clients,
        "stats": {
            "received": len(orders),
            "unique": len(clients),
            "duplicates_merged": valid_count - len(clients),
            "invalid_dropped": invalid_dropped,
        },
    }


@app.get("/")
async def root():
    return JSONResponse({"service": "order-sync", "endpoint": "/api/clients"})


@app.get("/api/clients")
async def clients():
    return await synchronize()


@app.get("/health")
async def health():
    return {"status": "ok"}
