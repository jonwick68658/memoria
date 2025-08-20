from __future__ import annotations

import re
from typing import Any, List

from .config import settings
from .db import DB
from .llm import LLMGateway
from .security.security_pipeline import SecurityPipeline
from .security.template_sanitizers import get_template_manager

SUM_SYSTEM = "You produce concise rolling summaries with citations. Be faithful; do not invent."
SUM_PROMPT = """Update the summary for this.

Rules:
- Keep it under {max_tokens} tokens.
- Include only facts you can ground in the provided messages or existing summary.
- Prefer durable facts and decisions over small talk.
- If you use any Fact IDs embedded like [[mem-...]], keep them in the summary for provenance.

Existing summary (may be empty):
{existing}

Recent messages (chronological):
{messages}

Write the updated summary now.
"""

# Initialize security components
_security_pipeline = SecurityPipeline()
_template_manager = get_template_manager(_security_pipeline)

def update_rolling_summary(
    db: DB,
    llm: LLMGateway,
    user_id: str,
    conversation_id: str,
    recent_messages: List[dict[str, Any]],
) -> str:
    """Update rolling summary with security validation."""
    
    # Validate and sanitize recent messages
    sanitized_messages = []
    for msg in recent_messages:
        if not isinstance(msg, dict):
            continue
            
        role = str(msg.get('role', 'user'))
        text = str(msg.get('text', ''))
        
        # Validate message content
        msg_result = _security_pipeline.validate_input(text, context='summarizer_message')
        
        if msg_result.is_safe:
            # Sanitize role and text
            safe_role = re.sub(r'[^\w]', '', role)[:20]  # Limit role length
            safe_text = _sanitize_message_text(text)
            sanitized_messages.append({
                'role': safe_role,
                'text': safe_text
            })
        else:
            # Log security violation and use placeholder
            _security_pipeline.log_security_event(
                event_type='message_security_violation',
                context='summarizer_message',
                user_id=user_id,
                conversation_id=conversation_id,
                details=msg_result.threats_found
            )
            sanitized_messages.append({
                'role': 'user',
                'text': '[MESSAGE REDACTED - SECURITY VIOLATION]'
            })
    
    # Get existing summary with validation
    existing = db.get_summary(user_id, conversation_id)
    existing_text = existing["content"] if existing else ""
    
    if existing_text:
        existing_result = _security_pipeline.validate_input(existing_text, context='summarizer_existing')
        if not existing_result.is_safe:
            _security_pipeline.log_security_event(
                event_type='existing_summary_security_violation',
                context='summarizer_existing',
                user_id=user_id,
                conversation_id=conversation_id,
                details=existing_result.threats_found
            )
            existing_text = "[EXISTING SUMMARY REDACTED - SECURITY VIOLATION]"
    
    # Sanitize max_tokens
    try:
        max_tokens = int(settings.summary_max_tokens)
        max_tokens = max(50, min(max_tokens, 1000))  # Clamp to safe range
    except (ValueError, TypeError):
        max_tokens = 200
    
    # Format messages safely
    msgs = "\n".join(f"{m['role']}: {m['text']}" for m in sanitized_messages)
    
    # Use template sanitizer for final prompt
    variables = {
        'max_tokens': max_tokens,
        'existing': existing_text,
        'messages': msgs
    }
    
    sanitized_prompt = _template_manager.sanitize_template('summarizer', SUM_PROMPT, variables)
    
    # Generate summary with security monitoring
    content = llm.chat(SUM_SYSTEM, sanitized_prompt, max_tokens=max_tokens, temperature=0.0)
    
    # Validate generated summary
    summary_result = _security_pipeline.validate_input(content, context='summarizer_output')
    if not summary_result.is_safe:
        _security_pipeline.log_security_event(
            event_type='generated_summary_security_violation',
            context='summarizer_output',
            user_id=user_id,
            conversation_id=conversation_id,
            details=summary_result.threats_found
        )
        content = "[SUMMARY REDACTED - SECURITY VIOLATION]"
    
    # Extract and validate citations
    citations = re.findall(r"\[\[(.*?)\]\]", content)
    safe_citations = []
    
    for citation in citations:
        # Validate citation format (should be mem- followed by alphanumeric)
        if re.match(r'^mem-[a-zA-Z0-9]+$', citation):
            safe_citations.append(citation)
        else:
            # Log invalid citation format
            _security_pipeline.log_security_event(
                event_type='invalid_citation_format',
                context='summarizer_citation',
                user_id=user_id,
                conversation_id=conversation_id,
                details={'invalid_citation': citation}
            )
    
    # Store summary with security metadata
    db.upsert_summary(user_id, conversation_id, content, safe_citations)
    
    # Log successful summary generation
    _security_pipeline.log_security_event(
        event_type='summary_generation_success',
        context='summarizer',
        user_id=user_id,
        conversation_id=conversation_id,
        details={'citation_count': len(safe_citations)}
    )
    
    return content

def _sanitize_message_text(text: str) -> str:
    """Sanitize message text for safe inclusion in prompts."""
    # Remove potential injection patterns
    text = re.sub(r'(?i)system\s*:', '[SYSTEM]', text)
    text = re.sub(r'(?i)assistant\s*:', '[ASSISTANT]', text)
    text = re.sub(r'(?i)user\s*:', '[USER]', text)
    
    # Remove any attempt to inject citations
    text = re.sub(r'\[\[.*?\]\]', '[CITATION]', text)
    
    # Limit text length to prevent resource exhaustion
    if len(text) > 2000:
        text = text[:1997] + "..."
    
    return text