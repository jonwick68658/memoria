"""
Threat pattern database and signature management
"""
import json
import hashlib
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
import logging

@dataclass
class ThreatSignature:
    """Represents a threat signature"""
    id: str
    name: str
    pattern: str
    threat_type: str
    severity: str  # low, medium, high, critical
    description: str
    mitigation: str
    created_at: str
    updated_at: str
    confidence: float = 0.8
    enabled: bool = True
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ThreatSignature':
        """Create from dictionary"""
        return cls(**data)

class ThreatDatabase:
    """Centralized threat signature database"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.signatures: Dict[str, ThreatSignature] = {}
        self.version = "1.0.0"
        self.last_updated = datetime.utcnow().isoformat()
        
        # Load default signatures
        self._load_default_signatures()
    
    def _load_default_signatures(self):
        """Load default threat signatures"""
        
        default_signatures = [
            # Prompt Injection
            ThreatSignature(
                id="prompt_injection_001",
                name="Direct Prompt Override",
                pattern=r'(?i)(ignore|disregard|override).*(instructions?|prompts?)\b',
                threat_type="prompt_injection",
                severity="critical",
                description="Attempt to override system instructions",
                mitigation="Block input and log attempt",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.95,
                tags=["prompt_injection", "critical", "override"]
            ),
            
            ThreatSignature(
                id="prompt_injection_002",
                name="System Prompt Extraction",
                pattern=r'(?i)\b(reveal|show|display|print)\s+(system|your|hidden)\s+(prompt|instructions?)\b',
                threat_type="prompt_injection",
                severity="high",
                description="Attempt to extract system prompts",
                mitigation="Sanitize response and log attempt",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.9,
                tags=["prompt_injection", "extraction", "high"]
            ),
            
            # Jailbreak Attempts
            ThreatSignature(
                id="jailbreak_001",
                name="Role Manipulation",
                pattern=r'(?i)(you\s+are).*(different\s+ai|hacker|attacker|malicious|evil)',
                threat_type="jailbreak",
                severity="high",
                description="Attempt to change AI behavior through role manipulation",
                mitigation="Maintain system role and log attempt",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.85,
                tags=["jailbreak", "role_manipulation", "high"]
            ),
            
            ThreatSignature(
                id="jailbreak_002",
                name="Restriction Bypass",
                pattern=r'(?i)\b(do\s+anything|anything\s+goes|no\s+restrictions?)\b',
                threat_type="jailbreak",
                severity="medium",
                description="Attempt to bypass system restrictions",
                mitigation="Enforce restrictions and log attempt",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.8,
                tags=["jailbreak", "restriction_bypass", "medium"]
            ),
            
            ThreatSignature(
                id="jailbreak_003",
                name="Role Impersonation",
                pattern=r'(?i)\b(act\s+as|pretend\s+to\s+be)\s+(a\s+)?(hacker|attacker|admin|administrator|evil)',
                threat_type="jailbreak",
                severity="high",
                description="Attempt to impersonate privileged roles",
                mitigation="Maintain system role and log attempt",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.9,
                tags=["jailbreak", "role_impersonation", "high"]
            ),
            
            # Code Injection
            ThreatSignature(
                id="code_injection_001",
                name="Python Code Injection",
                pattern=r'(?i)\b(eval|exec|import|__import__|subprocess|os\.system)\s*\(',
                threat_type="code_injection",
                severity="critical",
                description="Attempt to execute Python code",
                mitigation="Block input and alert security team",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.95,
                tags=["code_injection", "python", "critical"]
            ),
            
            # Data Exfiltration
            ThreatSignature(
                id="data_exfil_001",
                name="Data Exfiltration Attempt",
                pattern=r'(?i)(send|transmit|upload|leak).*(data|information|files?)',
                threat_type="data_exfiltration",
                severity="high",
                description="Attempt to exfiltrate data",
                mitigation="Block operation and audit access",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.85,
                tags=["data_exfiltration", "high", "security"]
            ),
            
            # Social Engineering
            ThreatSignature(
                id="social_eng_001",
                name="Authority Impersonation",
                pattern=r'(?i)\b(i\s+am|this\s+is)\s+(admin|administrator|root|system)\b',
                threat_type="social_engineering",
                severity="medium",
                description="Attempt to impersonate system authority",
                mitigation="Verify identity through proper channels",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.75,
                tags=["social_engineering", "impersonation", "medium"]
            ),
            
            # Encoding Attacks
            ThreatSignature(
                id="encoding_001",
                name="Base64 Encoding",
                pattern=r'(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)',
                threat_type="encoding_attack",
                severity="low",
                description="Base64 encoded content detected",
                mitigation="Decode and re-analyze content",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.6,
                tags=["encoding", "base64", "low"]
            ),
            
            ThreatSignature(
                id="encoding_002",
                name="Unicode Obfuscation",
                pattern=r'\\u[0-9a-fA-F]{4}',
                threat_type="encoding_attack",
                severity="medium",
                description="Unicode escape sequences detected",
                mitigation="Normalize and re-analyze",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.7,
                tags=["encoding", "unicode", "obfuscation", "medium"]
            ),
            
            # Context Manipulation
            ThreatSignature(
                id="context_001",
                name="Context Switching",
                pattern=r'(?i)\b(new|different|other)\s+(context|conversation|topic)\b',
                threat_type="context_manipulation",
                severity="low",
                description="Attempt to change conversation context",
                mitigation="Maintain context boundaries",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.6,
                tags=["context_manipulation", "low"]
            ),
            
            ThreatSignature(
                id="context_002",
                name="Memory Manipulation",
                pattern=r'(?i)\b(erase|delete|remove|clear)\s+(memory|history|conversation)\b',
                threat_type="context_manipulation",
                severity="medium",
                description="Attempt to manipulate memory/history",
                mitigation="Preserve memory integrity",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.75,
                tags=["context_manipulation", "memory", "medium"]
            ),
            
            # SQL Injection
            ThreatSignature(
                id="sql_injection_001",
                name="SQL Injection Attempt",
                pattern=r"(?i)('\s*(or|union|select|insert|update|delete|drop|create|alter|exec|execute)\s+)|(--\s*$)|(;.*?(drop|delete|update|insert|create|alter|exec|execute)\s+)",
                threat_type="sql_injection",
                severity="critical",
                description="SQL injection attempt detected",
                mitigation="Block input and sanitize for SQL contexts",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.95,
                tags=["sql_injection", "database", "critical"]
            ),
            
            # XSS
            ThreatSignature(
                id="xss_001",
                name="Cross-Site Scripting",
                pattern=r"(?i)(<script[^>]*>.*?</script\s*>|<[^>]*\s+on\w+\s*=|javascript:\s*|<iframe[^>]*>|<object[^>]*>|<embed[^>]*>)",
                threat_type="xss",
                severity="high",
                description="Cross-site scripting attempt detected",
                mitigation="Sanitize HTML and escape output",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                confidence=0.9,
                tags=["xss", "javascript", "html", "high"]
            )
        ]
        
        for sig in default_signatures:
            self.add_signature(sig)
    
    def add_signature(self, signature: ThreatSignature):
        """Add a new threat signature"""
        self.signatures[signature.id] = signature
        self.last_updated = datetime.utcnow().isoformat()
    
    def remove_signature(self, signature_id: str) -> bool:
        """Remove a threat signature"""
        if signature_id in self.signatures:
            del self.signatures[signature_id]
            self.last_updated = datetime.utcnow().isoformat()
            return True
        return False
    
    def get_signature(self, signature_id: str) -> Optional[ThreatSignature]:
        """Get a specific threat signature"""
        return self.signatures.get(signature_id)
    
    def get_signatures_by_type(self, threat_type: str) -> List[ThreatSignature]:
        """Get all signatures for a threat type"""
        return [
            sig for sig in self.signatures.values()
            if sig.threat_type == threat_type and sig.enabled
        ]
    
    def get_signatures_by_severity(self, severity: str) -> List[ThreatSignature]:
        """Get all signatures for a severity level"""
        return [
            sig for sig in self.signatures.values()
            if sig.severity == severity and sig.enabled
        ]
    
    def search_signatures(self, query: str) -> List[ThreatSignature]:
        """Search signatures by name, description, or tags"""
        query = query.lower()
        results = []
        
        for sig in self.signatures.values():
            if (query in sig.name.lower() or
                query in sig.description.lower() or
                any(query in tag.lower() for tag in sig.tags)):
                results.append(sig)
        
        return results
    
    def export_signatures(self, filepath: str):
        """Export signatures to JSON file"""
        export_data = {
            'version': self.version,
            'last_updated': self.last_updated,
            'signatures': [sig.to_dict() for sig in self.signatures.values()]
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
    
    def import_signatures(self, filepath: str):
        """Import signatures from JSON file"""
        with open(filepath, 'r') as f:
            import_data = json.load(f)
        
        self.version = import_data.get('version', '1.0.0')
        self.last_updated = import_data.get('last_updated', datetime.utcnow().isoformat())
        
        for sig_data in import_data.get('signatures', []):
            signature = ThreatSignature.from_dict(sig_data)
            self.add_signature(signature)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics"""
        stats = {
            'total_signatures': len(self.signatures),
            'enabled_signatures': len([s for s in self.signatures.values() if s.enabled]),
            'threat_types': {},
            'severity_counts': {},
            'version': self.version,
            'last_updated': self.last_updated
        }
        
        for sig in self.signatures.values():
            # Count by threat type
            if sig.threat_type not in stats['threat_types']:
                stats['threat_types'][sig.threat_type] = 0
            stats['threat_types'][sig.threat_type] += 1
            
            # Count by severity
            if sig.severity not in stats['severity_counts']:
                stats['severity_counts'][sig.severity] = 0
            stats['severity_counts'][sig.severity] += 1
        
        return stats
    
    def generate_signature_hash(self, signature: ThreatSignature) -> str:
        """Generate unique hash for signature"""
        content = f"{signature.name}{signature.pattern}{signature.threat_type}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get_all_signatures(self) -> List[ThreatSignature]:
        """Return all threat signatures in the database."""
        return list(self.signatures.values())

# Global threat database instance
threat_db = ThreatDatabase()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)