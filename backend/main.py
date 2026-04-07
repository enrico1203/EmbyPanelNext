from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from database import engine, Base
import models  # noqa: F401 — registra tutti i modelli prima del create_all
from routers import auth_router, admin_router, reseller_router, prezzi_router, movimenti_router, scheduler_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Streaming Panel Next API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://reseller.emby.at",
        "http://localhost:9090",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router, prefix="/auth", tags=["Auth"])
app.include_router(admin_router.router, prefix="/admin", tags=["Admin"])
app.include_router(reseller_router.router, prefix="/reseller", tags=["Reseller"])
app.include_router(prezzi_router.router, prefix="/admin", tags=["Admin"])
app.include_router(movimenti_router.router, prefix="", tags=["Movimenti"])
app.include_router(scheduler_router.router, prefix="/admin", tags=["Scheduler"])


@app.get("/health")
def health():
    return {"status": "ok"}
