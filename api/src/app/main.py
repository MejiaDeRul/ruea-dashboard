from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse
from .core.config import settings
from .routers import public, admin
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title=settings.APP_NAME, default_response_class=ORJSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://127.0.0.1:5173","*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["GET","POST","OPTIONS"], allow_headers=["*"]
)

@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}

app.include_router(public.router)
app.include_router(admin.router)
