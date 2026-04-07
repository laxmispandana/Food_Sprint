import base64
import hashlib
import hmac

import requests
from flask import current_app


RAZORPAY_ORDER_URL = "https://api.razorpay.com/v1/orders"


def razorpay_configured():
    return bool(
        current_app.config.get("RAZORPAY_KEY_ID")
        and current_app.config.get("RAZORPAY_KEY_SECRET")
    )


def create_razorpay_order(local_order):
    credentials = (
        f"{current_app.config['RAZORPAY_KEY_ID']}:{current_app.config['RAZORPAY_KEY_SECRET']}"
    )
    auth_header = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    payload = {
        "amount": int(local_order.total_amount * 100),
        "currency": "INR",
        "receipt": f"foodsprint-{local_order.id}",
        "notes": {"local_order_id": str(local_order.id)},
    }
    response = requests.post(
        RAZORPAY_ORDER_URL,
        headers={
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    secret = current_app.config["RAZORPAY_KEY_SECRET"].encode("utf-8")
    message = f"{razorpay_order_id}|{razorpay_payment_id}".encode("utf-8")
    generated_signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(generated_signature, razorpay_signature)
