"""Razorpay integration (test mode) with HMAC signature verification."""
import hashlib
import hmac

import razorpay

from app import config


def create_razorpay_order(amount_rupees: float, receipt: str) -> dict:
    client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))
    return client.order.create({
        "amount": int(round(amount_rupees * 100)),  # paise
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 1,
    })


def verify_signature(razorpay_order_id: str, razorpay_payment_id: str, signature: str) -> bool:
    payload = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    expected = hmac.new(config.RAZORPAY_KEY_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
