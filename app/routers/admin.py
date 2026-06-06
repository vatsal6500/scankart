import csv
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin, templates
from app.models import Order, Outlet, Product
from app.routers.pages import _qr_data_uri

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("")
def dashboard(request: Request, db: Session = Depends(get_db)):
    stats = {
        "products": db.query(func.count(Product.id)).scalar(),
        "orders": db.query(func.count(Order.id)).filter(Order.status == "paid").scalar(),
        "revenue": db.query(func.coalesce(func.sum(Order.total), 0)).filter(Order.status == "paid").scalar(),
        "low_stock": db.query(func.count(Product.id)).filter(Product.stock < 10, Product.active.is_(True)).scalar(),
    }
    recent = db.query(Order).order_by(Order.created_at.desc()).limit(8).all()
    return templates.TemplateResponse(request, "admin/dashboard.html", {"stats": stats, "recent": recent})


@router.get("/products")
def products(request: Request, outlet_id: int | None = None, db: Session = Depends(get_db)):
    outlets = db.query(Outlet).all()
    outlet_id = outlet_id or (outlets[0].id if outlets else 0)
    items = (
        db.query(Product)
        .filter(Product.outlet_id == outlet_id, Product.active.is_(True))
        .order_by(Product.category, Product.name)
        .all()
    )
    return templates.TemplateResponse(
        request, "admin/products.html",
        {"products": items, "outlets": outlets, "outlet_id": outlet_id},
    )


@router.post("/products")
def create_product(
    outlet_id: int = Form(...),
    barcode: str = Form(...),
    name: str = Form(...),
    category: str = Form("General"),
    price: float = Form(...),
    gst_percent: float = Form(18.0),
    emoji: str = Form("🛒"),
    stock: int = Form(0),
    db: Session = Depends(get_db),
):
    db.add(Product(
        outlet_id=outlet_id, barcode=barcode.strip(), name=name.strip(),
        category=category.strip(), price=price, gst_percent=gst_percent,
        emoji=emoji.strip() or "🛒", stock=stock,
    ))
    db.commit()
    return RedirectResponse(f"/admin/products?outlet_id={outlet_id}", status_code=303)


SAMPLE_CSV = """barcode,name,category,price,gst_percent,emoji,stock
8901719110018,Parle Monaco Classic 200g,Snacks,30,18,🍘,100
8901058851826,Nescafe Classic 50g,Beverages,225,18,☕,40
8901030865278,Lifebuoy Soap 125g,Personal Care,38,18,🧼,150
"""


@router.get("/products/sample-csv")
def sample_csv():
    return Response(
        content=SAMPLE_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="scankart_products_sample.csv"'},
    )


@router.post("/products/import")
async def import_products(
    outlet_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not db.get(Outlet, outlet_id):
        raise HTTPException(404, "Outlet not found")
    text = (await file.read()).decode("utf-8-sig", errors="replace")  # utf-8-sig: tolerate Excel BOM
    reader = csv.DictReader(io.StringIO(text))
    created = updated = skipped = 0
    for row in reader:
        try:
            barcode = (row.get("barcode") or "").strip()
            name = (row.get("name") or "").strip()
            price = float(row.get("price"))
            gst_percent = float(row.get("gst_percent") or 18)
            stock = int(float(row.get("stock") or 0))
            if not barcode or not name or price < 0 or not (0 <= gst_percent <= 28) or stock < 0:
                raise ValueError
        except (TypeError, ValueError):
            skipped += 1
            continue
        category = (row.get("category") or "General").strip() or "General"
        emoji = (row.get("emoji") or "🛒").strip() or "🛒"
        existing = (
            db.query(Product)
            .filter(Product.outlet_id == outlet_id, Product.barcode == barcode)
            .first()
        )
        if existing:
            existing.name, existing.category = name, category
            existing.price, existing.gst_percent = price, gst_percent
            existing.emoji, existing.stock = emoji, stock
            existing.active = True  # re-activate if it was soft-deleted
            updated += 1
        else:
            db.add(Product(
                outlet_id=outlet_id, barcode=barcode, name=name, category=category,
                price=price, gst_percent=gst_percent, emoji=emoji, stock=stock,
            ))
            created += 1
    db.commit()
    return RedirectResponse(
        f"/admin/products?outlet_id={outlet_id}&imported={created}&updated={updated}&skipped={skipped}",
        status_code=303,
    )


@router.post("/products/{product_id}/update")
def update_product(
    product_id: int,
    name: str = Form(...),
    category: str = Form("General"),
    price: float = Form(...),
    gst_percent: float = Form(18.0),
    emoji: str = Form("🛒"),
    stock: int = Form(0),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404)
    product.name, product.category = name.strip(), category.strip()
    product.price, product.gst_percent = price, gst_percent
    product.emoji, product.stock = emoji.strip() or "🛒", stock
    db.commit()
    return RedirectResponse(f"/admin/products?outlet_id={product.outlet_id}", status_code=303)


@router.post("/products/{product_id}/delete")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(404)
    product.active = False  # soft delete: keeps past order history intact
    db.commit()
    return RedirectResponse(f"/admin/products?outlet_id={product.outlet_id}", status_code=303)


@router.get("/orders")
def orders(request: Request, db: Session = Depends(get_db)):
    items = db.query(Order).order_by(Order.created_at.desc()).limit(100).all()
    return templates.TemplateResponse(request, "admin/orders.html", {"orders": items})


@router.get("/barcodes")
def barcodes(request: Request, outlet_id: int | None = None, db: Session = Depends(get_db)):
    outlets = db.query(Outlet).all()
    outlet_id = outlet_id or (outlets[0].id if outlets else 0)
    items = (
        db.query(Product)
        .filter(Product.outlet_id == outlet_id, Product.active.is_(True))
        .order_by(Product.category, Product.name)
        .all()
    )
    # QR version of each barcode — laptop webcams read QR far better than 1-D barcodes
    qr_map = {p.id: _qr_data_uri(p.barcode) for p in items}
    return templates.TemplateResponse(
        request, "admin/barcodes.html",
        {"products": items, "outlets": outlets, "outlet_id": outlet_id, "qr_map": qr_map},
    )
