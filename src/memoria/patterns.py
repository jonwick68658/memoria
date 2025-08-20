from __future__ import annotations

import json
import re
from typing import Any, List, Optional

from .db import DB
from .llm import LLMGateway, EmbeddingClient
from .security.security_pipeline import SecurityPipeline
from .security.template_sanitizers import get_template_manager

INSIGHT_SYSTEM = "You are a pattern detector. Output JSON only."
INSIGHT_PROMPT = """Given the following memories, identify any patterns, themes, or insights that emerge.
Focus on recurring behaviors, preferences, relationships, or trends.

Output a JSON array of objects:
[
  {
    "type": "pattern|theme|insight",
    "title": "Short title",
    "description": "Detailed description",
    "evidence": ["memory_id_1", "memory_id_2", ...],
    "confidence": 0.0-1.0
  }
]

If no clear patterns emerge, output [].

Memories:
{mems}
"""

# Initialize security components
_security_pipeline = SecurityPipeline()
_template_manager = get_template_manager(_security_pipeline)

def generate_insights(
    db: DB,
    llm: LLMGateway,
    user_id: str,
    conversation_id: Optional[str] = None,
    limit: int = 100,
) -> List[dict[str, Any]]:
    """Generate insights from memories with security validation."""
    
    # Validate limit parameter
    try:
        limit = int(limit)
        limit = max(1, min(limit, 1000))  # Clamp to safe range
    except (ValueError, TypeError):
        limit = 100
    
    # Fetch memories with security considerations
    memories = db.get_memories(user_id, conversation_id=conversation_id, limit=limit)
    
    # Validate and sanitize memories
    sanitized_memories = []
    for mem in memories:
        if not isinstance(mem, dict):
            continue
            
        # Validate memory ID
        mem_id = str(mem.get('id', ''))
        if not re.match(r'^mem-[a-zA-Z0-9]+$', mem_id):
            # Generate safe ID
            mem_id = f"mem-{hash(str(mem)) % 1000000:06d}"
        
        # Validate memory text
        text = str(mem.get('text', ''))
        text_result = _security_pipeline.validate_input(text, context='patterns_memory')
        
        if text_result.is_safe:
            # Sanitize text
            safe_text = _sanitize_memory_text(text)
            sanitized_memories.append({
                'id': mem_id,
                'text': safe_text,
                'type': str(mem.get('type', 'fact'))[:20],  # Limit type length
                'created_at': str(mem.get('created_at', ''))[:19]  # ISO format
            })
        else:
            # Log security violation and use placeholder
            _security_pipeline.log_security_event(
                event_type='memory_security_violation',
                context='patterns_memory',
                user_id=user_id,
                conversation_id=conversation_id or 'global',
                details=text_result.threats_found
            )
            sanitized_memories.append({
                'id': mem_id,
                'text': '[MEMORY REDACTED - SECURITY VIOLATION]',
                'type': 'redacted',
                'created_at': str(mem.get('created_at', ''))[:19]
            })
    
    if not sanitized_memories:
        return []
    
    # Format memories safely for prompt
    formatted_memories = "\n".join(
        f"- [{m['id']}] {m['type']}: {m['text']}" for m in sanitized_memories
    )
    
    # Use template sanitizer for final prompt
    variables = {'mems': formatted_memories}
    sanitized_prompt = _template_manager.sanitize_template('patterns', INSIGHT_PROMPT, variables)
    
    # Generate insights with security monitoring
    raw_response = llm.chat(INSIGHT_SYSTEM, sanitized_prompt, max_tokens=1000, temperature=0.0)
    
    # Validate and parse response
    try:
        insights = json.loads(raw_response)
        if not isinstance(insights, list):
            insights = []
    except json.JSONDecodeError:
        # Log parsing error
        _security_pipeline.log_security_event(
            event_type='insight_parsing_error',
            context='patterns_output',
            user_id=user_id,
            conversation_id=conversation_id or 'global',
            details={'raw_response': raw_response[:200]}
        )
        insights = []
    
    # Validate and sanitize insights
    sanitized_insights = []
    for insight in insights:
        if not isinstance(insight, dict):
            continue
            
        # Validate insight structure
        insight_type = str(insight.get('type', ''))
        if insight_type not in {'pattern', 'theme', 'insight'}:
            insight_type = 'insight'
        
        title = str(insight.get('title', ''))
        description = str(insight.get('description', ''))
        
        # Validate title and description
        title_result = _security_pipeline.validate_input(title, context='patterns_insight_title')
        desc_result = _security_pipeline.validate_input(description, context='patterns_insight_description')
        
        if not (title_result.is_safe and desc_result.is_safe):
            _security_pipeline.log_security_event(
                event_type='insight_content_security_violation',
                context='patterns_insight',
                user_id=user_id,
                conversation_id=conversation_id or 'global',
                details={'title_safe': title_result.is_safe, 'desc_safe': desc_result.is_safe}
            )
            continue
        
        # Sanitize evidence
        evidence = insight.get('evidence', [])
        if isinstance(evidence, list):
            safe_evidence = []
            for ev in evidence:
                ev_str = str(ev)
                if re.match(r'^mem-[a-zA-Z0-9]+$', ev_str):
                    safe_evidence.append(ev_str)
        else:
            safe_evidence = []
        
        # Validate confidence
        try:
            confidence = float(insight.get('confidence', 0.5))
            confidence = max(0.0, min(1.0, confidence))
        except (ValueError, TypeError):
            confidence = 0.5
        
        # Create sanitized insight
        sanitized_insight = {
            'type': insight_type,
            'title': _sanitize_insight_text(title),
            'description': _sanitize_insight_text(description),
            'evidence': safe_evidence,
            'confidence': confidence
        }
        
        sanitized_insights.append(sanitized_insight)
    
    # Store insights with security metadata
    for insight in sanitized_insights:
        db.add_insight(
            user_id=user_id,
            conversation_id=conversation_id,
            insight=insight,
            provenance={"source": "pattern_analysis"}
        )
    
    # Log successful insight generation
    _security_pipeline.log_security_event(
        event_type='insight_generation_success',
        context='patterns',
        user_id=user_id,
        conversation_id=conversation_id or 'global',
        details={'insights_generated': len(sanitized_insights)}
    )
    
    return sanitized_insights

def _sanitize_memory_text(text: str) -> str:
    """Sanitize memory text for safe processing."""
    # Remove potential injection patterns
    text = re.sub(r'(?i)system\s*:', '[SYSTEM]', text)
    text = re.sub(r'(?i)instruction\s*:', '[INSTRUCTION]', text)
    text = re.sub(r'(?i)prompt\s*:', '[PROMPT]', text)
    
    # Remove any attempt to inject JSON or code
    text = re.sub(r'[{}[\]<>]', '', text)
    
    # Limit text length
    if len(text) > 500:
        text = text[:497] + "..."
    
    return text.strip()

def _sanitize_insight_text(text: str) -> str:
    """Sanitize insight text for safe storage."""
    # Remove potential injection patterns
    text = re.sub(r'(?i)system\s*:', '[SYSTEM]', text)
    text = re.sub(r'(?i)instruction\s*:', '[INSTRUCTION]', text)
    text = re.sub(r'(?i)prompt\s*:', '[PROMPT]', text)
    
    # Remove any attempt to inject JSON or code
    text = re.sub(r'[{}[\]<>]', '', text)
    
    # Limit text length
    if len(text) > 200:
        text = text[:197] + "..."
    
    return text.strip()