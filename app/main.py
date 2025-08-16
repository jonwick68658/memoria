from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, JSONResponse
from pydantic import BaseModel, Field

from memoria.config import settings, validate_settings
from memoria.sdk import MemoriaClient

logger = logging.getLogger("memoria.app")
logger.setLevel(settings.log_level)

validate_settings()

app = FastAPI(title="Memoria Gateway", version="1.0.0", default_response_class=ORJSONResponse)
client = MemoriaClient.create()

# ---------- Simple in-process rate limit (per API key) ----------
_rate_state: dict[str, tuple[float, float]] = {}  # key -> (last_ts, tokens)
RPS = settings.rate_limit_rps

def rate_limit(x_api_key: str) -> None:
    if not RPS or RPS <= 0:
        return
    now = time.time()
    last_ts, tokens = _rate_state.get(x_api_key, (now, RPS))
    elapsed = now - last_ts
    tokens = min(RPS, tokens + elapsed * RPS)
    if tokens < 1.0:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    tokens -= 1.0
    _rate_state[x_api_key] = (now, tokens)

# ---------- Middleware for Request ID ----------
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    req_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    start = time.time()
    response = await call_next(request)
    response.headers["X-Request-Id"] = req_id
    response.headers["X-Frame-Options"] = "DENY"
    logger.info("req_id=%s method=%s path=%s status=%s time_ms=%.2f",
                req_id, request.method, request.url.path, response.status_code, (time.time() - start) * 1000.0)
    return response

# ---------- Optional CORS (restrict as needed) ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],  # set specific origins if serving browsers
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# ---------- Pydantic schemas ----------
class ChatMsg(BaseModel):
    content: str = Field(..., description="User message text")

class ChatRequest(BaseModel):
    conversation_id: str
    message: ChatMsg

class ChatResponse(BaseModel):
    assistant_text: str
    cited_ids: list[str]
    assistant_message_id: Optional[str] = None

class CorrectionRequest(BaseModel):
    memory_id: str
    replacement_text: str

class InsightResponse(BaseModel):
    insight: str

# ---------- Auth helpers ----------
def auth(x_api_key: str = Header(..., alias="X-Api-Key")) -> str:
    if x_api_key != settings.gateway_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    rate_limit(x_api_key)
    return x_api_key

def get_user_id(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    return x_user_id

# ---------- Endpoints ----------
@app.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    try:
        resp = client.chat(user_id=user_id, conversation_id=req.conversation_id, question=req.message.content)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Chat failed")
        raise HTTPException(status_code=500, detail=str(exc))
    return JSONResponse(content=resp.model_dump())

@app.post("/correction")
def correction(
    req: CorrectionRequest,
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    try:
        client.correct(user_id=user_id, memory_id=req.memory_id, replacement_text=req.replacement_text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}

@app.get("/memories")
def list_memories(
    conversation_id: Optional[str] = None,
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    try:
        mems = client.db.get_recent_memories(user_id, conversation_id, limit=100)
        return {"memories": mems}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/insights/generate", response_model=InsightResponse)
def gen_insights(
    conversation_id: Optional[str] = None,
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    try:
        content = client.generate_insights(user_id=user_id, conversation_id=conversation_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"insight": content}

@app.get("/insights")
def get_insights(
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    try:
        items = client.db.get_insights(user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"insights": items}

@app.get("/healthz")
def healthz():
    try:
        with client.db.pool.connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "db": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# ---------- Graceful shutdown ----------
@app.on_event("shutdown")
def shutdown() -> None:
    client.db.pool.close()