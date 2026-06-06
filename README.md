# 🛒 ScanKart — Scan. Pay. Go.

Self-checkout demo: customers scan product barcodes with their phone camera,
build a cart, pay online (Razorpay test mode) and get a digital bill with an
exit-verification QR — no billing queue.

## Features

**Customer PWA** (mobile-first, installable)
- Select an outlet → scan barcodes (EAN-13 / UPC / Code-128 / QR) with the phone camera
- Browse/search catalog as a camera fallback, quantity steppers, live GST breakdown
- Razorpay test-mode checkout (or built-in demo gateway when no keys are configured)
- Digital bill with CGST/SGST split, transaction ID and exit-verification QR

**Admin panel** (`/admin`, HTTP Basic auth)
- Dashboard: products, paid orders, revenue, low-stock alerts
- Product CRUD with inline editing, stock auto-decrements on purchase
- **CSV bulk import** (upsert by barcode) with downloadable sample template —
  retailers can load their whole catalog in one upload
- Orders list, printable barcode sheet for demoing with paper stickers

**API** — auto-generated Swagger docs at `/docs`

## Run locally

```bash
python3.13 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000 (customer app) and http://localhost:8000/admin
(default credentials: `admin` / `scankart123`).

> 📷 **Camera note:** browsers only allow camera access on `https://` or
> `localhost`. To test scanning from a phone on your LAN, use a tunnel like
> `npx localtunnel --port 8000` or deploy to Render.

## Run with Docker

```bash
docker compose up --build
# or
docker build -t scankart . && docker run -p 8000:8000 scankart
```

## Enable real Razorpay test checkout

1. Create a free account at https://dashboard.razorpay.com
2. Switch to **Test Mode** → Settings → API Keys → Generate key
3. Set environment variables:

```bash
export RAZORPAY_KEY_ID=rzp_test_xxxxxxxx
export RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxx
```

Test UPI: `success@razorpay` · Test card: `4111 1111 1111 1111`, any future
expiry, any CVV. Without keys, the app automatically uses its built-in demo
payment screen, so the end-to-end flow always works.

## Deploy to Render (free tier)

1. Push this repo to GitHub/GitLab
2. Render → **New → Web Service** → connect the repo
3. Runtime: **Docker** (Render auto-detects the `Dockerfile`)
4. Add env vars `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` (optional) and
   `ADMIN_PASSWORD`
5. Deploy → you get an `https://scankart-xxxx.onrender.com` URL — open it on
   any phone and scan away (HTTPS means the camera works out of the box)

> Free tier note: the instance sleeps when idle (~30 s cold start) and the
> SQLite file is ephemeral — data re-seeds on restart, which is fine for demos.

## Demo script (for client meetings)

1. Open `/admin/barcodes`, print the sheet, stick barcodes on real products
2. On a phone, open the app → pick the outlet → **Scan a product**
3. Scan a few barcodes → cart fills up → adjust quantities
4. **Pay & checkout** → test UPI/card → digital bill appears
5. Open the bill's **exit QR** with a second phone → staff sees "BILL VERIFIED"
6. Back on `/admin` → revenue and stock updated live

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | _(empty)_ | Enable Razorpay test checkout |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / `scankart123` | Admin panel auth |
| `DATABASE_URL` | `sqlite:///./scankart.db` | Swap to Postgres for persistence |
| `PORT` | `8000` | Injected by Render |

## Stack

FastAPI · SQLAlchemy · SQLite · Jinja2 · Tailwind CSS · html5-qrcode ·
JsBarcode · Razorpay · Docker
