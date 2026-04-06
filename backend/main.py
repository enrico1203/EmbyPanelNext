from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from routers import auth_router, admin_router, reseller_router

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


@app.get("/health")
def health():
    return {"status": "ok"}
