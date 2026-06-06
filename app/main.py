from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config
from app.database import Base, SessionLocal, engine
from app.routers import admin, api, pages
from app.seed import seed_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=f"{config.APP_NAME} API",
    description="Scan & Go self-checkout platform — scan products in-store, "
    "pay online, skip the queue.",
    version="0.1.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(api.router)
app.include_router(pages.router)
app.include_router(admin.router)
