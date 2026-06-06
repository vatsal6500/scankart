import secrets
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def gen_order_id() -> str:
    return "SK" + uuid.uuid4().hex[:10].upper()


def gen_exit_token() -> str:
    return secrets.token_urlsafe(8)


class Outlet(Base):
    __tablename__ = "outlets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(255), default="")
    emoji: Mapped[str] = mapped_column(String(8), default="🏬")

    products: Mapped[list["Product"]] = relationship(back_populates="outlet")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    barcode: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(60), default="General")
    price: Mapped[float] = mapped_column(Float)  # MRP, GST-inclusive
    gst_percent: Mapped[float] = mapped_column(Float, default=18.0)
    emoji: Mapped[str] = mapped_column(String(8), default="🛒")
    image_url: Mapped[str] = mapped_column(String(500), default="")
    stock: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    outlet: Mapped["Outlet"] = relationship(back_populates="products")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(16), primary_key=True, default=gen_order_id)
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|paid|failed
    payment_mode: Mapped[str] = mapped_column(String(16), default="mock")  # razorpay|mock
    razorpay_order_id: Mapped[str] = mapped_column(String(64), default="")
    razorpay_payment_id: Mapped[str] = mapped_column(String(64), default="")
    subtotal: Mapped[float] = mapped_column(Float, default=0.0)   # taxable value
    gst_amount: Mapped[float] = mapped_column(Float, default=0.0)
    total: Mapped[float] = mapped_column(Float, default=0.0)
    exit_token: Mapped[str] = mapped_column(String(24), default=gen_exit_token)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    outlet: Mapped["Outlet"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    name: Mapped[str] = mapped_column(String(150))      # snapshot at purchase time
    barcode: Mapped[str] = mapped_column(String(32))
    emoji: Mapped[str] = mapped_column(String(8), default="🛒")
    unit_price: Mapped[float] = mapped_column(Float)
    gst_percent: Mapped[float] = mapped_column(Float)
    qty: Mapped[int] = mapped_column(Integer)
    line_total: Mapped[float] = mapped_column(Float)

    order: Mapped["Order"] = relationship(back_populates="items")
