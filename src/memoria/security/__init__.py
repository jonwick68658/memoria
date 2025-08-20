"""
Memoria Security Package - Comprehensive security framework for AI applications

This package provides multi-layered security protection against:
- Prompt injection attacks
- Code injection attempts
- Data exfiltration
- Social engineering attacks
- Context manipulation
- Encoding-based attacks

Main Components:
- SecurityPipeline: Main orchestrator for security checks
- InputValidator: Validates and sanitizes user input
- SemanticAnalyzer: Advanced semantic analysis for threat detection
- ThreatDatabase: Centralized threat signature management
"""

from .security_pipeline import SecurityPipeline, SecurityResult, SecurityCheck
from .input_validator import InputValidator, ValidationResult
from .semantic_analyzer import SemanticAnalyzer, SemanticAnalysisResult
from .threat_database import ThreatDatabase, ThreatSignature, threat_db

__version__ = "1.0.0"
__author__ = "Memoria Security Team"

# Export main components
__all__ = [
    # Main pipeline
    'SecurityPipeline',
    'SecurityResult',
    'SecurityCheck',
    
    # Input validation
    'InputValidator',
    'ValidationResult',
    
    # Semantic analysis
    'SemanticAnalyzer',
    'SemanticAnalysisResult',
    
    # Threat database
    'ThreatDatabase',
    'ThreatSignature',
    'threat_db',
    
    # Global instances
    'security_pipeline',
]

# Global instances for convenience
from .security_pipeline import security_pipeline

# Configure package-level logging
import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())