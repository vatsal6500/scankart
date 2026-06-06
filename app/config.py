import os

APP_NAME = "ScanKart"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./scankart.db")

# Razorpay test-mode keys. If not set, the app falls back to a built-in mock payment screen.
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "scankart123")


def razorpay_enabled() -> bool:
    return bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)
