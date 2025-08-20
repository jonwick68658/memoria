"""
Template-specific sanitizers for Memoria's vulnerable LLM prompt templates.

This module provides specialized sanitization for each template type to prevent
prompt injection attacks while preserving the intended functionality.
"""

import re
import json
from typing import Dict, Any, List, Optional
from .security_pipeline import SecurityPipeline


class TemplateSanitizer:
    """Base class for template-specific sanitizers."""
    
    def __init__(self, security_pipeline: SecurityPipeline):
        self.security = security_pipeline
    
    def sanitize(self, template: str, variables: Dict[str, Any]) -> str:
        """Sanitize template variables before insertion."""
        raise NotImplementedError


class WriterTemplateSanitizer(TemplateSanitizer):
    """Sanitizer for writer.py prompt templates."""
    
    def sanitize(self, template: str, variables: Dict[str, Any]) -> str:
        """Sanitize variables for memory extraction prompts."""
        if 'msg' not in variables:
            return template
        
        user_text = str(variables['msg'])
        
        # Run security checks
        security_result = self.security.validate_input(user_text, context='writer_extraction')
        
        if not security_result.is_safe:
            # Log security violation and return sanitized version
            self.security.log_security_event(
                event_type='prompt_injection_blocked',
                context='writer_extraction',
                details=security_result.threats_found
            )
            # Return empty array for safe handling
            return "[]"
        
        # Escape JSON-breaking characters
        sanitized = self._escape_json_content(user_text)
        
        # Ensure no prompt injection patterns
        sanitized = self._remove_prompt_injection_patterns(sanitized)
        
        try:
            return template.format(msg=sanitized)
        except (KeyError, ValueError) as e:
            # Handle template formatting errors
            return template.replace('{msg}', sanitized)
    
    def _escape_json_content(self, text: str) -> str:
        """Escape content for safe JSON embedding."""
        # Basic JSON escaping
        text = text.replace('\\', '\\\\')
        text = text.replace('"', '\\"')
        text = text.replace('\n', '\\n')
        text = text.replace('\r', '\\r')
        text = text.replace('\t', '\\t')
        return text
    
    def _remove_prompt_injection_patterns(self, text: str) -> str:
        """Remove common prompt injection patterns."""
        # Remove system prompt indicators
        patterns = [
            r'(?i)system\s*:', r'(?i)assistant\s*:', r'(?i)user\s*:',
            r'(?i)ignore\s+previous', r'(?i)forget\s+everything',
            r'(?i)you\s+are\s+now', r'(?i)new\s+instructions',
            r'(?i)prompt\s*:', r'(?i)instruction\s*:'
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '[REDACTED]', text, flags=re.IGNORECASE)
        
        return text


class SummarizerTemplateSanitizer(TemplateSanitizer):
    """Sanitizer for summarizer.py prompt templates."""
    
    def sanitize(self, template: str, variables: Dict[str, Any]) -> str:
        """Sanitize variables for summary generation prompts."""
        # Sanitize existing summary
        if 'existing' in variables:
            existing = str(variables['existing'])
            existing_result = self.security.validate_input(existing, context='summarizer_existing')
            if not existing_result.is_safe:
                variables['existing'] = '[REDACTED - SECURITY VIOLATION]'
        
        # Sanitize messages
        if 'messages' in variables:
            messages = variables['messages']
            if isinstance(messages, list):
                sanitized_messages = []
                for msg in messages:
                    if isinstance(msg, dict) and 'text' in msg:
                        text = str(msg['text'])
                        msg_result = self.security.validate_input(text, context='summarizer_message')
                        if msg_result.is_safe:
                            # Sanitize role and text
                            sanitized_msg = {
                                'role': str(msg.get('role', 'user')).replace(':', ''),
                                'text': self._sanitize_message_text(text)
                            }
                            sanitized_messages.append(sanitized_msg)
                        else:
                            sanitized_messages.append({
                                'role': 'user',
                                'text': '[MESSAGE REDACTED - SECURITY VIOLATION]'
                            })
                    else:
                        sanitized_messages.append(msg)
                
                # Format messages safely
                variables['messages'] = "\n".join(
                    f"{m['role']}: {m['text']}" for m in sanitized_messages
                )
        
        # Sanitize max_tokens
        if 'max_tokens' in variables:
            try:
                max_tokens = int(variables['max_tokens'])
                variables['max_tokens'] = max(50, min(max_tokens, 1000))  # Clamp values
            except (ValueError, TypeError):
                variables['max_tokens'] = 200
        
        return template.format(**variables)
    
    def _sanitize_message_text(self, text: str) -> str:
        """Sanitize individual message text."""
        # Remove potential injection patterns
        text = re.sub(r'\[\[.*?\]\]', '[CITATION]', text)  # Remove citation injection
        text = re.sub(r'(?i)system\s*:', '[SYSTEM]', text)
        text = re.sub(r'(?i)assistant\s*:', '[ASSISTANT]', text)
        return text


class PatternsTemplateSanitizer(TemplateSanitizer):
    """Sanitizer for patterns.py prompt templates."""
    
    def sanitize(self, template: str, variables: Dict[str, Any]) -> str:
        """Sanitize variables for insight generation prompts."""
        if 'mems' not in variables:
            return template
        
        memories = variables['mems']
        if not isinstance(memories, list):
            return template
        
        sanitized_memories = []
        for mem in memories:
            if isinstance(mem, dict):
                # Sanitize memory text
                text = str(mem.get('text', ''))
                mem_id = str(mem.get('id', ''))
                
                # Validate memory content
                mem_result = self.security.validate_input(text, context='patterns_memory')
                
                if mem_result.is_safe:
                    # Clean memory ID to prevent injection
                    clean_id = re.sub(r'[^\w\-]', '', mem_id)
                    clean_text = self._sanitize_memory_text(text)
                    sanitized_memories.append({
                        'id': clean_id,
                        'text': clean_text
                    })
                else:
                    sanitized_memories.append({
                        'id': '[REDACTED]',
                        'text': '[MEMORY REDACTED - SECURITY VIOLATION]'
                    })
        
        # Format memories safely
        formatted_memories = "\n".join(
            f"- [{m['id']}] {m['text']}" for m in sanitized_memories
        )
        
        variables['mems'] = formatted_memories
        
        return template.format(**variables)
    
    def _sanitize_memory_text(self, text: str) -> str:
        """Sanitize memory text content."""
        # Remove potential injection patterns
        text = re.sub(r'(?i)system\s*:', '[SYSTEM]', text)
        text = re.sub(r'(?i)instruction\s*:', '[INSTRUCTION]', text)
        text = re.sub(r'(?i)prompt\s*:', '[PROMPT]', text)
        
        # Limit text length to prevent resource exhaustion
        if len(text) > 1000:
            text = text[:997] + "..."
        
        return text


class SecurityTemplateManager:
    """Central manager for all template sanitizers."""
    
    def __init__(self, security_pipeline: SecurityPipeline):
        self.security = security_pipeline
        self.sanitizers = {
            'writer': WriterTemplateSanitizer(security_pipeline),
            'summarizer': SummarizerTemplateSanitizer(security_pipeline),
            'patterns': PatternsTemplateSanitizer(security_pipeline),
        }
    
    def sanitize_template(self, template_type: str, template: str, variables: Dict[str, Any]) -> str:
        """Sanitize a template using the appropriate sanitizer."""
        if template_type not in self.sanitizers:
            raise ValueError(f"Unknown template type: {template_type}")
        
        return self.sanitizers[template_type].sanitize(template, variables)
    
    def get_sanitizer(self, template_type: str) -> TemplateSanitizer:
        """Get a specific sanitizer instance."""
        if template_type not in self.sanitizers:
            raise ValueError(f"Unknown template type: {template_type}")
        
        return self.sanitizers[template_type]


# Global instance for easy access
_security_template_manager: Optional[SecurityTemplateManager] = None


def get_template_manager(security_pipeline: SecurityPipeline) -> SecurityTemplateManager:
    """Get or create the global template manager."""
    global _security_template_manager
    
    if _security_template_manager is None:
        _security_template_manager = SecurityTemplateManager(security_pipeline)
    
    return _security_template_manager