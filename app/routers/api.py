from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import config, payment
from app.database import get_db
from app.models import Order, OrderItem, Outlet, Product

router = APIRouter(prefix="/api", tags=["api"])


# ---------- schemas ----------

class ProductOut(BaseModel):
    id: int
    barcode: str
    name: str
    category: str
    price: float
    gst_percent: float
    emoji: str
    image_url: str
    stock: int

    class Config:
        from_attributes = True


class CartItem(BaseModel):
    product_id: int
    qty: int = Field(gt=0, le=99)


class CheckoutRequest(BaseModel):
    outlet_id: int
    items: list[CartItem] = Field(min_length=1)


class VerifyRequest(BaseModel):
    order_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


# ---------- catalog ----------

@router.get("/outlets")
def list_outlets(db: Session = Depends(get_db)):
    return [
        {"id": o.id, "name": o.name, "address": o.address, "emoji": o.emoji}
        for o in db.query(Outlet).all()
    ]


@router.get("/outlets/{outlet_id}/products", response_model=list[ProductOut])
def list_products(outlet_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Product)
        .filter(Product.outlet_id == outlet_id, Product.active.is_(True))
        .order_by(Product.category, Product.name)
        .all()
    )


@router.get("/outlets/{outlet_id}/products/by-barcode/{barcode}", response_model=ProductOut)
def product_by_barcode(outlet_id: int, barcode: str, db: Session = Depends(get_db)):
    product = (
        db.query(Product)
        .filter(
            Product.outlet_id == outlet_id,
            Product.barcode == barcode.strip(),
            Product.active.is_(True),
        )
        .first()
    )
    if not product:
        raise HTTPException(404, "Product not found in this outlet")
    return product


# ---------- checkout & payment ----------

def _gst_split(price: float, gst_percent: float) -> tuple[float, float]:
    """MRP is GST-inclusive: split into taxable value and GST amount."""
    taxable = round(price / (1 + gst_percent / 100), 2)
    return taxable, round(price - taxable, 2)


@router.post("/checkout")
def checkout(payload: CheckoutRequest, db: Session = Depends(get_db)):
    outlet = db.get(Outlet, payload.outlet_id)
    if not outlet:
        raise HTTPException(404, "Outlet not found")

    order = Order(outlet_id=outlet.id)
    subtotal = gst_amount = total = 0.0
    for item in payload.items:
        product = db.get(Product, item.product_id)
        if not product or product.outlet_id != outlet.id or not product.active:
            raise HTTPException(400, f"Invalid product in cart: {item.product_id}")
        if product.stock < item.qty:
            raise HTTPException(409, f"Only {product.stock} left in stock for {product.name}")
        line_total = round(product.price * item.qty, 2)
        taxable, gst = _gst_split(line_total, product.gst_percent)
        subtotal += taxable
        gst_amount += gst
        total += line_total
        order.items.append(OrderItem(
            product_id=product.id,
            name=product.name,
            barcode=product.barcode,
            emoji=product.emoji,
            unit_price=product.price,
            gst_percent=product.gst_percent,
            qty=item.qty,
            line_total=line_total,
        ))

    order.subtotal = round(subtotal, 2)
    order.gst_amount = round(gst_amount, 2)
    order.total = round(total, 2)

    if config.razorpay_enabled():
        order.payment_mode = "razorpay"
        rzp_order = payment.create_razorpay_order(order.total, receipt=order.id)
        order.razorpay_order_id = rzp_order["id"]
        db.add(order)
        db.commit()
        return {
            "mode": "razorpay",
            "order_id": order.id,
            "key_id": config.RAZORPAY_KEY_ID,
            "razorpay_order_id": order.razorpay_order_id,
            "amount_paise": int(round(order.total * 100)),
            "total": order.total,
            "outlet_name": outlet.name,
        }

    db.add(order)
    db.commit()
    return {"mode": "mock", "order_id": order.id, "total": order.total}


def _mark_paid(order: Order, db: Session) -> None:
    order.status = "paid"
    order.paid_at = datetime.utcnow()
    for item in order.items:
        product = db.get(Product, item.product_id)
        if product:
            product.stock = max(0, product.stock - item.qty)
    db.commit()


@router.post("/payment/verify")
def verify_payment(payload: VerifyRequest, db: Session = Depends(get_db)):
    order = db.get(Order, payload.order_id)
    if not order or order.razorpay_order_id != payload.razorpay_order_id:
        raise HTTPException(404, "Order not found")
    if order.status == "paid":
        return {"status": "paid", "bill_url": f"/bill/{order.id}"}
    if not payment.verify_signature(
        payload.razorpay_order_id, payload.razorpay_payment_id, payload.razorpay_signature
    ):
        order.status = "failed"
        db.commit()
        raise HTTPException(400, "Payment signature verification failed")
    order.razorpay_payment_id = payload.razorpay_payment_id
    _mark_paid(order, db)
    return {"status": "paid", "bill_url": f"/bill/{order.id}"}


@router.post("/payment/mock/{order_id}")
def mock_payment(order_id: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if order.payment_mode != "mock":
        raise HTTPException(400, "Order is not a mock-payment order")
    if order.status != "paid":
        order.razorpay_payment_id = "pay_MOCK" + order.id
        _mark_paid(order, db)
    return {"status": "paid", "bill_url": f"/bill/{order.id}"}
