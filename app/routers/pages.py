import base64
import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.deps import templates
from app.models import Order, Outlet

router = APIRouter(tags=["pages"])


@router.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    outlets = db.query(Outlet).all()
    return templates.TemplateResponse(request, "index.html", {"outlets": outlets})


@router.get("/shop/{outlet_id}")
def shop(request: Request, outlet_id: int, db: Session = Depends(get_db)):
    outlet = db.get(Outlet, outlet_id)
    if not outlet:
        raise HTTPException(404, "Outlet not found")
    return templates.TemplateResponse(
        request, "shop.html",
        {"outlet": outlet, "razorpay_enabled": config.razorpay_enabled()},
    )


@router.get("/pay/mock/{order_id}")
def mock_pay_page(request: Request, order_id: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status == "paid":
        return templates.TemplateResponse(request, "mockpay.html", {"order": order, "already_paid": True})
    return templates.TemplateResponse(request, "mockpay.html", {"order": order, "already_paid": False})


def _qr_data_uri(data: str) -> str:
    img = qrcode.make(data, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@router.get("/bill/{order_id}")
def bill(request: Request, order_id: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if order.status != "paid":
        raise HTTPException(403, "Order is not paid yet")
    verify_url = str(request.base_url).rstrip("/") + f"/exit/{order.id}/{order.exit_token}"
    return templates.TemplateResponse(
        request, "bill.html",
        {"order": order, "exit_qr": _qr_data_uri(verify_url)},
    )


@router.get("/exit/{order_id}/{token}")
def exit_verification(request: Request, order_id: str, token: str, db: Session = Depends(get_db)):
    """Staff-facing page: scanned at the store exit to verify the bill is genuine."""
    order = db.get(Order, order_id)
    valid = bool(order and order.exit_token == token and order.status == "paid")
    return templates.TemplateResponse(
        request, "exit.html", {"order": order if valid else None, "valid": valid},
    )
