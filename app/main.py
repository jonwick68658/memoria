from __future__ import annotations

import logging
import time
import uuid
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, JSONResponse
from pydantic import BaseModel, Field

from memoria.config import settings, validate_settings
from memoria.sdk import MemoriaClient
from app.tasks import process_memory_async, generate_insights_async, correct_memory_async
from app.celery_app import celery_app
from app.metrics import record_api_call, record_task_submission

logger = logging.getLogger("memoria.app")
logger.setLevel(settings.log_level)

validate_settings()

app = FastAPI(title="Memoria Gateway", version="2.0.0", default_response_class=ORJSONResponse)
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

class AsyncTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
    timestamp: datetime

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime

# ---------- Auth helpers ----------
def auth(x_api_key: str = Header(..., alias="X-Api-Key")) -> str:
    if x_api_key != settings.gateway_api_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
    rate_limit(x_api_key)
    return x_api_key

def get_user_id(x_user_id: str = Header(..., alias="X-User-Id")) -> str:
    return x_user_id

# ---------- Synchronous Endpoints (Legacy) ----------
@app.post("/chat", response_model=ChatResponse)
def chat(
    req: ChatRequest,
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    """Legacy synchronous chat endpoint - use /chat/async for async processing"""
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
    """Legacy synchronous correction endpoint - use /correction/async for async processing"""
    try:
        client.correct(user_id=user_id, memory_id=req.memory_id, replacement_text=req.replacement_text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}

@app.post("/insights/generate", response_model=InsightResponse)
def gen_insights(
    conversation_id: Optional[str] = None,
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    """Legacy synchronous insights endpoint - use /insights/generate/async for async processing"""
    try:
        content = client.generate_insights(user_id=user_id, conversation_id=conversation_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"insight": content}

# ---------- Asynchronous Endpoints ----------
@app.post("/chat/async", response_model=AsyncTaskResponse)
def chat_async(
    req: ChatRequest,
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    """Submit chat processing as an async task"""
    try:
        task = process_memory_async.delay(
            user_id=user_id,
            conversation_id=req.conversation_id,
            question=req.message.content
        )
        record_task_submission("chat_async")
        return AsyncTaskResponse(
            task_id=task.id,
            status="submitted",
            message="Chat processing started in background",
            timestamp=datetime.utcnow()
        )
    except Exception as exc:
        logger.exception("Failed to submit chat async task")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/correction/async", response_model=AsyncTaskResponse)
def correction_async(
    req: CorrectionRequest,
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    """Submit memory correction as an async task"""
    try:
        task = correct_memory_async.delay(
            user_id=user_id,
            memory_id=req.memory_id,
            replacement_text=req.replacement_text
        )
        record_task_submission("correction_async")
        return AsyncTaskResponse(
            task_id=task.id,
            status="submitted",
            message="Memory correction started in background",
            timestamp=datetime.utcnow()
        )
    except Exception as exc:
        logger.exception("Failed to submit correction async task")
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/insights/generate/async", response_model=AsyncTaskResponse)
def gen_insights_async(
    conversation_id: Optional[str] = None,
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    """Submit insights generation as an async task"""
    try:
        task = generate_insights_async.delay(
            user_id=user_id,
            conversation_id=conversation_id
        )
        record_task_submission("insights_async")
        return AsyncTaskResponse(
            task_id=task.id,
            status="submitted",
            message="Insights generation started in background",
            timestamp=datetime.utcnow()
        )
    except Exception as exc:
        logger.exception("Failed to submit insights async task")
        raise HTTPException(status_code=500, detail=str(exc))

# ---------- Task Status Endpoints ----------
@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(
    task_id: str,
    _=Depends(auth),
):
    """Get the status and result of an async task"""
    try:
        task = celery_app.AsyncResult(task_id)
        
        status_map = {
            "PENDING": "pending",
            "STARTED": "processing",
            "SUCCESS": "completed",
            "FAILURE": "failed",
            "RETRY": "retrying",
            "REVOKED": "cancelled"
        }
        
        response = TaskStatusResponse(
            task_id=task_id,
            status=status_map.get(task.status, "unknown"),
            timestamp=datetime.utcnow()
        )
        
        if task.ready():
            if task.successful():
                response.result = task.result
            else:
                response.error = str(task.result) if task.result else "Task failed"
        
        return response
        
    except Exception as exc:
        logger.exception("Failed to get task status")
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/tasks")
def list_tasks(
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    """List active tasks for a user (requires monitoring setup)"""
    try:
        # This would require more sophisticated task tracking
        # For now, return a placeholder response
        return {"message": "Task listing requires additional monitoring setup", "active_tasks": []}
    except Exception as exc:
        logger.exception("Failed to list tasks")
        raise HTTPException(status_code=500, detail=str(exc))

# ---------- Legacy Endpoints ----------
@app.get("/memories")
def list_memories(
    conversation_id: Optional[str] = None,
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    """List memories (synchronous - lightweight operation)"""
    try:
        mems = client.db.get_recent_memories(user_id, conversation_id, limit=100)
        record_api_call("list_memories")
        return {"memories": mems}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/insights")
def get_insights(
    _=Depends(auth),
    user_id: str = Depends(get_user_id),
):
    """Get insights (synchronous - lightweight operation)"""
    try:
        items = client.db.get_insights(user_id)
        record_api_call("get_insights")
        return {"insights": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# ---------- Health Checks ----------
@app.get("/healthz")
def healthz():
    """Basic health check"""
    try:
        with client.db.pool.connection() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok", "db": "ok"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/healthz/detailed")
def healthz_detailed():
    """Detailed health check including Celery"""
    try:
        # Check database
        with client.db.pool.connection() as conn:
            conn.execute("SELECT 1").fetchone()
        
        # Check Celery
        from celery import current_app
        inspect = current_app.control.inspect()
        active_workers = inspect.active() or {}
        
        return {
            "status": "ok",
            "db": "ok",
            "celery": {
                "workers": len(active_workers),
                "active_tasks": sum(len(tasks) for tasks in active_workers.values())
            }
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

# ---------- Graceful shutdown ----------
@app.on_event("shutdown")
def shutdown() -> None:
    client.db.pool.close()