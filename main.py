from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from .db import init_db
from .routers import identify, converse, documents, consult

app = FastAPI(
    title="MediKiosk API",
    description="AI-powered clinical history & document digitization kiosk - demo backend",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only; lock down to kiosk/physician-screen origins in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "medikiosk-api"}


app.include_router(identify.router)
app.include_router(converse.router)
app.include_router(documents.router)
app.include_router(consult.router)
