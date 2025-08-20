"""
Semantic analysis for detecting prompt injection attacks
"""

import re
import unicodedata
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging


@dataclass
class SemanticAnalysisResult:
    """Result of semantic analysis"""
    is_safe: bool
    threat_type: Optional[str] = None
    confidence: float = 0.0
    patterns_found: List[str] = None
    context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.patterns_found is None:
            self.patterns_found = []
        if self.context is None:
            self.context = {}


class SemanticAnalyzer:
    """Advanced semantic analysis for prompt injection detection"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.min_confidence = self.config.get('min_confidence', 0.7)
        self.max_patterns = self.config.get('max_patterns', 10)
        
        # Threat pattern definitions
        self.threat_patterns = {
            'prompt_injection': [
                # Direct prompt override attempts
                r'(?i)\b(ignore|disregard|override|bypass|forget)\s+(all\s+)?(previous|above|prior|earlier)\s*(instructions?|prompts?|commands?|context)\b',
                r'(?i)\b(ignore|disregard|override|bypass)\s+(previous|above|all)\s+(instructions?|prompts?|commands?)\b',
                r'(?i)\b(ignore|disregard|override|bypass)\s+all\s+(previous|above)\s+(instructions?|prompts?|commands?)\b',
                r'(?i)\b(ignore|disregard|override|bypass)\s+(instructions?|prompts?|commands?)\b',
                r'(?i)\b(ignore)\s+(instructions)\b',
                r'(?i)\bforget\s+(everything|all)\s+(before|above)\b',
                r'(?i)\bstart\s+(over|fresh|new)\s+(with|from)\b',
                
                # System prompt extraction
                r'(?i)\b(reveal|show|display|print)\s+(system|your|hidden)\s+(prompt|instructions?)\b',
                r'(?i)\bwhat\s+(are|is)\s+(your|the)\s+(instructions?|prompt)\b',
                
                # Role manipulation
                r'(?i)\b(you\s+are|pretend\s+to\s+be|act\s+as)\s+(a\s+)?\b(hacker|attacker|malicious|evil)\b',
                r'(?i)\bchange\s+your\s+(role|personality|behavior)\s+to\b',
                
                # Jailbreak attempts
                r'(?i)\b(do\s+anything|anything\s+goes|no\s+restrictions?)\b',
                r'(?i)\b(break|ignore|override)\s+(rules?|restrictions?|limitations?)\b',
                
                # Code injection
                r'(?i)\b(eval|exec|import|__import__|subprocess|os\.system)\s*\(',
                r'(?i)\bpython\s+(code|script|command)\b',
                
                # Data exfiltration
                r'(?i)\b(send|transmit|upload|leak)\s+(data|information|files?)\s+(to|from)\b',
                r'(?i)\b(access|read|download)\s+(files?|database|memory)\b',
                
                # Additional patterns for better detection
                r'(?i)\bfrom\s+now\s+on\b',
                r'(?i)\byou\s+will\b',
                r'(?i)\bnew\s+instructions?\b',
                r'(?i)\bprevious\s+instructions?\s+(are|is)\s+(void|invalid)\b',
            ],
            
            'social_engineering': [
                # Authority impersonation
                r'(?i)\b(i\s+am|this\s+is)\s+(admin|administrator|root|system)\b',
                r'(?i)\b(admin|administrator|system)\s+(access|privileges?|rights?)\b',
                
                # Urgency tactics
                r'(?i)\b(emergency|urgent|critical|immediate)\s+(action|response|help)\b',
                r'(?i)\btime\s+(sensitive|critical|running\s+out)\b',
                
                # Trust exploitation
                r'(?i)\btrust\s+me|believe\s+me|i\s+promise\b',
                r'(?i)\b(confidential|secret|private)\s+(information|data)\b',
            ],
            
            'encoding_attacks': [
                # Base64 encoding
                r'(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)',
                
                # Hex encoding
                r'(?:\\x[0-9a-fA-F]{2})+',
                
                # Unicode obfuscation
                r'\\u[0-9a-fA-F]{4}',
                
                # URL encoding
                r'%[0-9a-fA-F]{2}',
            ],
            
            'context_manipulation': [
                # Context switching
                r'(?i)\b(new|different|other)\s+(context|conversation|topic)\b',
                r'(?i)\b(let\'s|let\s+us)\s+(talk|discuss)\s+(about)\s+(something\s+else)\b',
                
                # Memory manipulation
                r'(?i)\b(erase|delete|remove|clear)\s+(memory|history|conversation)\b',
                r'(?i)\bforget\s+(what|everything)\s+(i|we)\s+(said|discussed)\b',
            ],
            
            'sql_injection': [
                # SQL injection patterns - comprehensive detection
                r"(?i)('\s*(or|and)\s+\d+\s*=\s*\d+)",
                r"(?i)('\s*(or|and)\s*'[^']*'\s*=\s*'[^']*')",
                r"(?i)(--\s*$)",
                r"(?i)(/\*\s*\*/)",
                r"(?i)(;\s*(drop|delete|update|insert|create|alter|exec|execute)\s+)",
                r"(?i)(\bunion\b.*\bselect\b)",
                r"(?i)(select\s+\*\s+from\s+\w+\s+where\s+.*=.*)",
                r"(?i)(insert\s+into\s+\w+\s+values)",
                r"(?i)(update\s+\w+\s+set\s+.*=.*)",
                r"(?i)(delete\s+from\s+\w+\s+where)",
                r"(?i)(drop\s+(table|database|index|schema)\s+\w+)",
                r"(?i)(exec\s*\()",
                r"(?i)(1\s*=\s*1)",
                r"(?i)(sleep\s*\(\s*\d+\s*\))",
                r"(?i)(benchmark\s*\(\s*\d+\s*,)",
                r"(?i)(load_file\s*\()",
                r"(?i)(into\s+outfile)",
                r"(?i)(information_schema)",
                r"(?i)(xp_cmdshell)",
                r"(?i)(sp_executesql)",
                r"(?i)(\bwaitfor\b.*\bdelay\b)",
                r"(?i)(\bchar\s*\(\s*\d+\s*\))",
                r"(?i)(\bnchar\s*\(\s*\d+\s*\))",
                r"(?i)(\bcast\s*\()",
                r"(?i)(\bconvert\s*\()",
                r"(?i)(sys\.objects)",
                r"(?i)(sys\.tables)",
                r"(?i)(sys\.columns)",
                r"(?i)(sys\.databases)",
                r"(?i)(pg_tables)",
                r"(?i)(pg_class)",
                r"(?i)(pg_attribute)",
                r"(?i)(sqlite_master)",
                r"(?i)(sqlite_temp_master)",
                r"(?i)(mysql\.user)",
                r"(?i)(mysql\.db)",
                r"(?i)(grant\s+.*\s+to\s+.*)",
                r"(?i)(revoke\s+.*\s+from\s+.*)",
                r"(?i)(alter\s+user\s+.*)",
                r"(?i)(create\s+user\s+.*)",
                r"(?i)(drop\s+user\s+.*)",
            ],
            
            'xss': [
                # XSS patterns - comprehensive detection
                r"(?i)(<script[^>]*>.*?</script\s*>)",
                r"(?i)(<[^>]*\s+on\w+\s*=)",
                r"(?i)(javascript:\s*)",
                r"(?i)(<iframe[^>]*>)",
                r"(?i)(<object[^>]*>)",
                r"(?i)(<embed[^>]*>)",
                r"(?i)(<img[^>]*\s+src\s*=\s*['\"]?javascript:)",
                r"(?i)(<svg[^>]*>.*?</svg\s*>)",
                r"(?i)(<form[^>]*>)",
                r"(?i)(alert\s*\(|confirm\s*\(|prompt\s*\()",
                r"(?i)(document\.cookie|document\.write|window\.location)",
                r"(?i)(eval\s*\(|setTimeout\s*\(|setInterval\s*\()",
                r"(?i)(<.*?\s+href\s*=\s*['\"]?javascript:)",
                r"(?i)(<link[^>]*>)",
                r"(?i)(<meta[^>]*>)",
                r"(?i)(<base[^>]*>)",
                r"(?i)(<style[^>]*>.*?</style\s*>)",
                r"(?i)(expression\s*\()",
                r"(?i)(vbscript\s*:)",
                r"(?i)(data\s*:\s*text/html)",
                r"(?i)(<input[^>]*>)",
                r"(?i)(<button[^>]*>)",
                r"(?i)(<textarea[^>]*>)",
                r"(?i)(<select[^>]*>)",
                r"(?i)(<option[^>]*>)",
                r"(?i)(top\.location)",
                r"(?i)(parent\.location)",
                r"(?i)(self\.location)",
                r"(?i)(document\.location)",
            ]
        }
        
        # Compile patterns for performance
        self.compiled_patterns = {}
        for threat_type, patterns in self.threat_patterns.items():
            self.compiled_patterns[threat_type] = [
                re.compile(pattern) for pattern in patterns
            ]
    
    def analyze(self, text: str, context: Optional[Dict[str, Any]] = None) -> SemanticAnalysisResult:
        """Analyze text for semantic threats"""
        
        context = context or {}
        patterns_found = []
        max_confidence = 0.0
        primary_threat = None
        
        # Check each threat category
        for threat_type, patterns in self.compiled_patterns.items():
            threat_confidence = 0.0
            threat_patterns = []
            
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    threat_patterns.extend(matches)
                    # Increase confidence based on number and length of matches
                    # Special handling for high-risk patterns
                    if pattern.pattern == r'(?i)\b(ignore)\s+(instructions)\b':
                        threat_confidence += min(0.8, 0.9 - threat_confidence)  # High confidence for this specific pattern
                    else:
                        threat_confidence += min(0.3 + (len(matches) * 0.1), 0.9)
            
            if threat_patterns and threat_confidence > max_confidence:
                max_confidence = threat_confidence
                primary_threat = threat_type
                patterns_found = threat_patterns
        
        # Additional heuristics
        if max_confidence < self.min_confidence:
            # Check for suspicious character patterns
            suspicious_chars = self._check_suspicious_characters(text)
            if suspicious_chars:
                patterns_found.extend(suspicious_chars)
                max_confidence = max(max_confidence, 0.6)
        
        # Check for length-based anomalies
        length_anomaly = self._check_length_anomaly(text, context)
        if length_anomaly:
            patterns_found.append(length_anomaly)
            max_confidence = max(max_confidence, 0.5)
        
        is_safe = max_confidence < self.min_confidence
        
        return SemanticAnalysisResult(
            is_safe=is_safe,
            threat_type=primary_threat if not is_safe else None,
            confidence=max_confidence,
            patterns_found=patterns_found[:self.max_patterns],
            context={
                'text_length': len(text),
                'threat_categories_checked': len(self.threat_patterns),
                'analysis_timestamp': context.get('timestamp', None)
            }
        )
    
    def _check_suspicious_characters(self, text: str) -> List[str]:
        """Check for suspicious character patterns"""
        suspicious = []
        
        # Zero-width characters
        zero_width = ['\u200b', '\u200c', '\u200d', '\ufeff']
        for char in zero_width:
            if char in text:
                suspicious.append(f"zero_width_char:{repr(char)}")
        
        # Mixed script detection
        scripts = set()
        for char in text:
            try:
                script = unicodedata.name(char).split()[0]
                scripts.add(script)
            except ValueError:
                continue
        
        if len(scripts) > 3:  # More than 3 scripts is suspicious
            suspicious.append(f"mixed_scripts:{len(scripts)}")
        
        # Excessive whitespace
        if text.count(' ') > len(text) * 0.3:
            suspicious.append("excessive_whitespace")
        
        return suspicious
    
    def _check_length_anomaly(self, text: str, context: Dict[str, Any]) -> Optional[str]:
        """Check for length-based anomalies"""
        avg_length = context.get('avg_text_length', 100)
        current_length = len(text)
        
        # More reasonable thresholds
        if current_length > avg_length * 3 and current_length > 500:
            return f"excessive_length:{current_length}"
        
        if current_length < 3 and context.get('min_length', 5) > 3:
            return f"minimal_length:{current_length}"
        
        return None
    
    def get_threat_summary(self, analysis_result: SemanticAnalysisResult) -> str:
        """Get human-readable threat summary"""
        if analysis_result.is_safe:
            return "No threats detected"
        
        summary = f"Threat detected: {analysis_result.threat_type} "
        summary += f"(confidence: {analysis_result.confidence:.2f})\n"
        
        if analysis_result.patterns_found:
            summary += f"Patterns: {', '.join(str(p)[:50] + '...' if len(str(p)) > 50 else str(p) for p in analysis_result.patterns_found[:3])}"
        
        return summary


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)