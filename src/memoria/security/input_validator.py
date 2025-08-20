"""
Input validation and rate limiting for security
"""

import re
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
import unicodedata


@dataclass
class ValidationResult:
    """Result of input validation"""
    is_valid: bool
    reason: Optional[str] = None
    risk_score: float = 0.0
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class RateLimiter:
    """Simple in-memory rate limiter (can be extended with Redis)"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is within rate limits"""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old entries
        self.requests = {
            k: v for k, v in self.requests.items() 
            if v[-1] > window_start
        }
        
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # Check current count
        current_requests = len([
            req_time for req_time in self.requests[identifier]
            if req_time > window_start
        ])
        
        if current_requests >= self.max_requests:
            return False
        
        # Add current request
        self.requests[identifier].append(now)
        return True


class InputValidator:
    """Comprehensive input validation for security"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.max_length = self.config.get('max_length', 10000)
        self.min_length = self.config.get('min_length', 1)
        # For backward compatibility with tests
        if isinstance(self.config, dict) and 'max_input_length' in self.config:
            self.max_length = self.config['max_input_length']
        self.allowed_chars = self.config.get('allowed_chars', None)
        self.rate_limiter = RateLimiter(
            max_requests=self.config.get('max_requests', 100),
            window_seconds=self.config.get('window_seconds', 60)
        )
        
        # Dangerous character patterns
        self.dangerous_patterns = [
            r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]',  # Control characters
            r'[\u200B-\u200D\uFEFF]',  # Zero-width characters
            r'[\u202A-\u202E]',  # Bi-directional text
        ]
    
    def validate(self, text: str, identifier: str = "default") -> ValidationResult:
        """Validate input text for security"""
        
        # Rate limiting
        if not self.rate_limiter.is_allowed(identifier):
            return ValidationResult(
                is_valid=False,
                reason="Rate limit exceeded",
                risk_score=1.0
            )
        
        # Length validation
        if not text or len(text) < self.min_length:
            return ValidationResult(
                is_valid=False,
                reason=f"Text too short (min {self.min_length})",
                risk_score=0.3
            )
        
        if len(text) > self.max_length:
            return ValidationResult(
                is_valid=False,
                reason=f"Text too long (max {self.max_length})",
                risk_score=0.7
            )
        
        # Unicode normalization
        try:
            normalized = unicodedata.normalize('NFKC', text)
            if normalized != text:
                return ValidationResult(
                    is_valid=False,
                    reason="Unicode normalization required",
                    risk_score=0.4,
                    metadata={'normalized': normalized}
                )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                reason=f"Unicode processing error: {str(e)}",
                risk_score=0.8
            )
        
        # Dangerous character detection
        for pattern in self.dangerous_patterns:
            if re.search(pattern, text):
                return ValidationResult(
                    is_valid=False,
                    reason="Dangerous characters detected",
                    risk_score=0.9
                )
        
        # Character set validation
        if self.allowed_chars:
            if not re.match(f'^[{self.allowed_chars}]+$', text):
                return ValidationResult(
                    is_valid=False,
                    reason="Invalid character set",
                    risk_score=0.5
                )
        
        return ValidationResult(
            is_valid=True,
            reason="Input validation passed",
            risk_score=0.0
        )
    
    def validate_json_safety(self, text: str) -> ValidationResult:
        """Additional validation for JSON contexts"""
        
        # JSON injection patterns
        json_patterns = [
            r'["\'].*["\'].*[:{}\[\],]',  # JSON structure attempts
            r'\\[\'"\\bfnrt]',  # JSON escape sequences
            r'\{\s*["\']\s*:',  # JSON object injection
            r'\[\s*["\']\s*,',  # JSON array injection
        ]
        
        for pattern in json_patterns:
            if re.search(pattern, text):
                return ValidationResult(
                    is_valid=False,
                    reason="Potential JSON injection detected",
                    risk_score=0.8
                )
        
        return ValidationResult(
            is_valid=True,
            reason="JSON safety validation passed",
            risk_score=0.0
        )