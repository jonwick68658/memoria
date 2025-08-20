from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .db import DB
from .llm import LLMGateway, EmbeddingClient
from .security.security_pipeline import SecurityPipeline
from .security.template_sanitizers import get_template_manager

EXTRACT_SYSTEM = "You are a precise extractor. Output JSON only."
EXTRACT_PROMPT = """From the user's latest message, extract durable, user-specific memories to store.
Only include: stable preferences, explicit corrections, facts about the user or their projects, decisions/plans with dates, or clear entities/relationships.
Do not include generic knowledge or assistant content.
Output a JSON array of objects: [
  {{"type": "preference|correction|fact|plan|entity|relation", "text": "...", "idempotency_key": "stable-key", "confidence": 0.0-1.0}}
]
If there are none, output [].

User message:
{msg}
"""

# Initialize security components
_security_pipeline = SecurityPipeline()
_template_manager = get_template_manager(_security_pipeline)

def _idem(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def maybe_write_memories(
    db: DB,
    llm: LLMGateway,
    user_id: str,
    conversation_id: str,
    user_text: str,
) -> list[str]:
    """Extract and store memories from user text with security validation."""
    
    # Validate input through security pipeline
    security_result = _security_pipeline.validate_input(user_text, context='writer_extraction')
    
    if not security_result.is_safe:
        # Log security violation and return empty list
        _security_pipeline.log_security_event(
            event_type='prompt_injection_blocked',
            context='writer_extraction',
            user_id=user_id,
            conversation_id=conversation_id,
            details=security_result.threats_found
        )
        return []
    
    # Sanitize template using template-specific sanitizer
    sanitized_prompt = _template_manager.sanitize_template(
        'writer', 
        EXTRACT_PROMPT, 
        {'msg': user_text}
    )
    
    # Additional validation for JSON safety
    try:
        # Ensure the sanitized prompt is safe for JSON processing
        json.dumps(sanitized_prompt)
    except (TypeError, ValueError):
        # If JSON serialization fails, use a safe fallback
        sanitized_prompt = EXTRACT_PROMPT.format(msg="[CONTENT SANITIZED]")
    
    raw = llm.chat(EXTRACT_SYSTEM, sanitized_prompt, max_tokens=500, temperature=0.0)
    
    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []

    mem_ids: list[str] = []
    for it in items:
        text = (it.get("text") or "").strip()
        type_ = (it.get("type") or "fact").strip()
        confidence = float(it.get("confidence", 0.8))
        
        if not text or confidence < 0.6:
            continue
            
        # Validate extracted text for security
        text_result = _security_pipeline.validate_input(text, context='writer_extracted_text')
        if not text_result.is_safe:
            _security_pipeline.log_security_event(
                event_type='extracted_text_security_violation',
                context='writer_extraction',
                user_id=user_id,
                conversation_id=conversation_id,
                details=text_result.threats_found
            )
            continue
            
        # Validate type for security
        if type_ not in {"preference", "correction", "fact", "plan", "entity", "relation"}:
            type_ = "fact"  # Default to safe type
            
        # Ensure confidence is within safe bounds
        confidence = max(0.0, min(1.0, confidence))
        
        idem = it.get("idempotency_key") or _idem(f"{user_id}|{text.lower()}")
        
        # Validate idempotency key
        if not re.match(r'^[a-f0-9]{16}$', idem):
            idem = _idem(f"{user_id}|{text.lower()}")
        
        emb = EmbeddingClient().embed(text)
        mid = db.add_memory(
            user_id=user_id,
            conversation_id=conversation_id,
            text=text,
            embedding=emb,
            type_=type_,
            importance=0.6 if type_ in ("preference", "plan") else 0.5,
            confidence=confidence,
            idempotency_key=idem,
            provenance={"source": "user_message"},
        )
        mem_ids.append(mid)
    
    # Log successful memory extraction
    _security_pipeline.log_security_event(
        event_type='memory_extraction_success',
        context='writer_extraction',
        user_id=user_id,
        conversation_id=conversation_id,
        details={'memories_extracted': len(mem_ids)}
    )
    
    return mem_ids