"""
FastAPI backend for VanityApp (production-ready skeleton).
This file expects db.py, payments.py and bot.py to be present in the same folder.
"""

import os, hmac, hashlib, json, urllib.parse
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import requests

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

import db
import payments
import bot as bot_module

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN environment variable required")

TELEGRAM_BOT_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI(title="VanityApp Backend")

def verify_telegram_init_data(init_data: str):
    params = {}
    for part in init_data.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = urllib.parse.unquote_plus(v)
    if "hash" not in params:
        raise ValueError("No hash in init_data")
    items = [f"{k}={params[k]}" for k in sorted(params) if k != "hash"]
    data_check_string = "\n".join(items)
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if computed != params["hash"]:
        raise ValueError("Invalid init_data")
    return params

def send_bot_message(chat_id: int, text: str, parse_mode="HTML"):
    try:
        r = requests.post(f"{TELEGRAM_BOT_API}/sendMessage", json={
            "chat_id": chat_id, "text": text, "parse_mode": parse_mode
        }, timeout=10)
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_media_via_bot(chat_id: int, file_paths: List[str], caption: Optional[str]=None):
    for idx, path in enumerate(file_paths[:2]):
        try:
            with open(path, "rb") as f:
                fname = os.path.basename(path)
                if fname.lower().endswith((".jpg",".jpeg",".png")):
                    files = {"photo": (fname, f)}
                    data = {"chat_id": chat_id}
                    if idx == 0 and caption:
                        data["caption"] = caption; data["parse_mode"]="HTML"
                    requests.post(f"{TELEGRAM_BOT_API}/sendPhoto", data=data, files=files, timeout=30)
                else:
                    files = {"video": (fname, f)}
                    data = {"chat_id": chat_id}
                    if idx == 0 and caption:
                        data["caption"] = caption; data["parse_mode"]="HTML"
                    requests.post(f"{TELEGRAM_BOT_API}/sendVideo", data=data, files=files, timeout=30)
        except Exception:
            pass

class CheckoutItem(BaseModel):
    product_id: int
    quantity: int = 1

class CheckoutPayload(BaseModel):
    telegram_id: int
    items: List[CheckoutItem]
    metadata: Optional[dict] = None

@app.post("/auth/verify")
async def auth_verify(payload: dict):
    init_data = payload.get("initData")
    if not init_data:
        raise HTTPException(400, "initData required")
    try:
        params = verify_telegram_init_data(init_data)
    except Exception as e:
        raise HTTPException(400, f"Invalid init_data: {e}")
    user = {}
    if "user" in params:
        try:
            user = json.loads(params["user"])
        except Exception:
            user = {"id": int(params.get("user_id") or 0)}
    else:
        uid = params.get("user_id") or params.get("id")
        if not uid:
            raise HTTPException(400, "No user info")
        user = {"id": int(uid)}
    telegram_id = int(user["id"])
    username = user.get("username")
    first_name = user.get("first_name","")
    db_user = db.get_or_create_user(telegram_id, username=username, first_name=first_name)
    if not db_user.get("deposit_address"):
        payments.get_or_create_deposit_address(db_user["id"])
        db_user = db.get_user_by_telegram_id(telegram_id)
    return {"ok": True, "user": db_user}

@app.get("/products")
async def list_products():
    prods = db.get_products(active_only=True)
    for p in prods:
        folder = os.path.join(os.getcwd(), "locimg", f"product_{p['id']}")
        p["media_urls"] = []
        if os.path.isdir(folder):
            for fname in sorted(os.listdir(folder))[:6]:
                p["media_urls"].append(f"/media/product_{p['id']}/{fname}")
    return {"ok": True, "products": prods}

@app.get("/products/{product_id}")
async def product_detail(product_id: int):
    p = db.get_product(product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    folder = os.path.join(os.getcwd(), "locimg", f"product_{p['id']}")
    media = []
    if os.path.isdir(folder):
        for fname in sorted(os.listdir(folder)):
            media.append(f"/media/product_{p['id']}/{fname}")
    p["media_urls"] = media
    return {"ok": True, "product": p}

@app.get("/media/product_{product_id}/{filename}")
async def serve_media(product_id: int, filename: str):
    path = os.path.join(os.getcwd(), "locimg", f"product_{product_id}", filename)
    if not os.path.exists(path):
        raise HTTPException(404, "File not found")
    return FileResponse(path)

@app.post("/cart/checkout")
async def checkout(payload: CheckoutPayload):
    telegram_id = payload.telegram_id
    items = payload.items
    user = db.get_user_by_telegram_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")
    total = 0.0
    for it in items:
        prod = db.get_product(it.product_id)
        if not prod:
            raise HTTPException(400, f"Product {it.product_id} unavailable")
        price = float(prod["price_sol"]) * it.quantity
        if user.get("referred_by"):
            discount = float(db.get_setting("referral_discount_percent","5"))
            price = price * (1 - discount/100.0)
        total += price
    if user["balance_sol"] < total:
        return {"ok": False, "error": "Insufficient balance", "balance": user["balance_sol"], "required": total}
    db.update_balance(user["id"], -total)
    orders=[]
    for it in items:
        prod = db.get_product(it.product_id)
        final_price = float(prod["price_sol"]) * it.quantity
        if user.get("referred_by"):
            discount = float(db.get_setting("referral_discount_percent","5"))
            final_price = final_price * (1 - discount/100.0)
        if prod.get("stock",-1) != -1:
            for _ in range(it.quantity):
                db.decrease_stock(prod["id"])
        order_id = db.create_order(user["id"], prod["id"], final_price)
        db.record_transaction(user["id"], f"order_{order_id}", final_price, "purchase", order_id)
        if user.get("referred_by"):
            commission_pct = float(db.get_setting("referral_commission_percent","5"))
            commission = float(prod["price_sol"]) * (commission_pct/100.0) * it.quantity
            db.update_balance(user["referred_by"], commission)
            db.record_transaction(user["referred_by"], f"ref_{order_id}", commission, "referral_comm", order_id)
            ref = db.get_user_by_id(user["referred_by"])
            if ref:
                send_bot_message(ref["telegram_id"], f"You earned {commission:.6f} SOL from a referral purchase.")
        folder = os.path.join(os.getcwd(), "locimg", f"product_{prod['id']}")
        chosen=[]
        if os.path.isdir(folder):
            files = sorted([f for f in os.listdir(folder) if f.lower().endswith(('.jpg','.jpeg','.png','.mp4'))])
            for f in files[:2]:
                chosen.append(os.path.join(folder,f))
        if chosen:
            send_media_via_bot(telegram_id, chosen, caption=prod.get("name"))
        db.mark_order_delivered(order_id)
        orders.append({"order_id": order_id, "product_id": prod["id"], "price": final_price})
    user_now = db.get_user_by_telegram_id(telegram_id)
    send_bot_message(telegram_id, f"✅ Purchase complete! Total: {total:.6f} SOL. New balance: {user_now['balance_sol']:.6f} SOL")
    return {"ok": True, "orders": orders, "balance": user_now["balance_sol"]}

@app.get("/user/{telegram_id}/balance")
async def get_balance(telegram_id: int):
    u = db.get_user_by_telegram_id(telegram_id)
    if not u:
        raise HTTPException(404, "User not found")
    if not u.get("deposit_address"):
        payments.get_or_create_deposit_address(u["id"])
    return {"ok": True, "user": u, "deposit_address": u.get("deposit_address")}
