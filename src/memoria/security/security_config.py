"""
Enterprise Security Configuration for Memoria
Provides centralized configuration management for all security components.
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from pathlib import Path

@dataclass
class SecurityConfig:
    """Centralized security configuration management."""
    
    # Input Validation
    max_input_length: int = 10000
    max_tokens_per_request: int = 4000
    allowed_characters: str = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,!?;:'\"-()[]{}@#$%^&*+=_<>/\\|"
    
    # Rate Limiting
    enable_rate_limiting: bool = True
    requests_per_minute: int = 60
    burst_limit: int = 10
    rate_limit_window: int = 60
    
    # Threat Detection
    threat_score_threshold: float = 0.7
    similarity_threshold: float = 0.85
    semantic_analysis_enabled: bool = True
    pattern_matching_enabled: bool = True
    
    # Monitoring
    enable_monitoring: bool = True
    log_level: str = "INFO"
    log_file: str = "logs/security.log"
    max_log_size_mb: int = 50
    log_retention_days: int = 7
    enable_security_logging: bool = True
    health_check_interval: int = 60
    max_requests_per_minute: int = 100
    
    # Alerting
    enable_alerts: bool = True
    alert_webhook_url: Optional[str] = None
    alert_email: Optional[str] = None
    alert_threshold: float = 0.9
    
    # Performance
    enable_caching: bool = True
    cache_ttl: int = 300
    async_processing: bool = True
    max_concurrent_requests: int = 100
    
    # Input validation configuration
    input_validation: Dict[str, Any] = field(default_factory=dict)
    
    # Template-specific settings
    writer_config: Dict[str, Any] = field(default_factory=dict)
    summarizer_config: Dict[str, Any] = field(default_factory=dict)
    patterns_config: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize template-specific configurations."""
        if not self.input_validation:
            self.input_validation = {
                'enabled': True,
                'max_length': 10000,
                'allowed_patterns': []
            }
        
        if not self.writer_config:
            self.writer_config = {
                "max_memories_per_extraction": 10,
                "min_confidence_score": 0.5,
                "max_memory_length": 500,
                "sanitize_json": True
            }
        
        if not self.summarizer_config:
            self.summarizer_config = {
                "max_summary_length": 1000,
                "min_summary_length": 50,
                "max_citations": 10,
                "sanitize_output": True
            }
        
        if not self.patterns_config:
            self.patterns_config = {
                "max_insights": 20,
                "min_confidence_score": 0.6,
                "max_evidence_length": 200,
                "sanitize_insights": True
            }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        keys = key.split('.')
        value = self
        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            elif isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access."""
        if isinstance(key, str):
            return getattr(self, key)
        raise TypeError(f"attribute name must be string, not '{type(key).__name__}'")

class SecurityConfigManager:
    """Manages security configuration with environment variable support."""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or os.getenv("SECURITY_CONFIG_FILE", "security_config.json")
        self.config = self._load_config()
    
    def _load_config(self) -> SecurityConfig:
        """Load configuration from file and environment variables."""
        config_data = {}
        
        # Load from file if exists
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config file {self.config_file}: {e}")
        
        # Override with environment variables
        env_mappings = {
            'SECURITY_MAX_INPUT_LENGTH': ('max_input_length', int),
            'SECURITY_THREAT_SCORE_THRESHOLD': ('threat_score_threshold', float),
            'SECURITY_SIMILARITY_THRESHOLD': ('similarity_threshold', float),
            'SECURITY_ENABLE_RATE_LIMITING': ('enable_rate_limiting', bool),
            'SECURITY_REQUESTS_PER_MINUTE': ('requests_per_minute', int),
            'SECURITY_LOG_LEVEL': ('log_level', str),
            'SECURITY_ALERT_WEBHOOK_URL': ('alert_webhook_url', str),
            'SECURITY_ALERT_EMAIL': ('alert_email', str),
            'SECURITY_ENABLE_MONITORING': ('enable_monitoring', bool),
            'SECURITY_ENABLE_CACHING': ('enable_caching', bool),
            'SECURITY_ASYNC_PROCESSING': ('async_processing', bool),
        }
        
        for env_var, (config_key, type_func) in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                if type_func == bool:
                    config_data[config_key] = value.lower() in ('true', '1', 'yes', 'on')
                else:
                    config_data[config_key] = type_func(value)
        
        return SecurityConfig(**config_data)
    
    def save_config(self, config: Optional[SecurityConfig] = None) -> None:
        """Save configuration to file."""
        if config is None:
            config = self.config
        
        # Ensure directory exists
        config_path = Path(self.config_file)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save configuration
        with open(self.config_file, 'w') as f:
            json.dump(asdict(config), f, indent=2)
    
    def get_config(self) -> SecurityConfig:
        """Get current configuration."""
        return self.config
    
    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration with new values."""
        config_dict = asdict(self.config)
        config_dict.update(updates)
        self.config = SecurityConfig(**config_dict)
        self.save_config()
    
    def get_template_config(self, template_name: str) -> Dict[str, Any]:
        """Get template-specific configuration."""
        template_configs = {
            'writer': self.config.writer_config,
            'summarizer': self.config.summarizer_config,
            'patterns': self.config.patterns_config
        }
        return template_configs.get(template_name, {})

# Global configuration instance
_config_manager = None

def get_security_config() -> SecurityConfig:
    """Get global security configuration."""
    global _config_manager
    if _config_manager is None:
        _config_manager = SecurityConfigManager()
    return _config_manager.get_config()

def reload_security_config() -> SecurityConfig:
    """Reload configuration from file and environment."""
    global _config_manager
    _config_manager = SecurityConfigManager()
    return _config_manager.get_config()

# Environment-specific configurations
ENVIRONMENT_CONFIGS = {
    'development': SecurityConfig(
        log_level='DEBUG',
        enable_monitoring=True,
        enable_rate_limiting=False,
        threat_score_threshold=0.5
    ),
    'staging': SecurityConfig(
        log_level='INFO',
        enable_monitoring=True,
        enable_rate_limiting=True,
        threat_score_threshold=0.7
    ),
    'production': SecurityConfig(
        log_level='WARNING',
        enable_monitoring=True,
        enable_rate_limiting=True,
        threat_score_threshold=0.8,
        max_input_length=5000,
        requests_per_minute=30
    )
}

def get_environment_config(environment: Optional[str] = None) -> SecurityConfig:
    """Get configuration for specific environment."""
    if environment is None:
        environment = os.getenv('ENVIRONMENT', 'development').lower()
    
    return ENVIRONMENT_CONFIGS.get(environment, ENVIRONMENT_CONFIGS['development'])

# Validation utilities
def validate_config(config: SecurityConfig) -> bool:
    """Validate security configuration."""
    validations = [
        (0 < config.max_input_length <= 50000, "max_input_length must be 1-50000"),
        (0 <= config.threat_score_threshold <= 1, "threat_score_threshold must be 0-1"),
        (0 <= config.similarity_threshold <= 1, "similarity_threshold must be 0-1"),
        (config.requests_per_minute > 0, "requests_per_minute must be positive"),
        (config.max_log_size_mb > 0, "max_log_size_mb must be positive"),
        (config.log_retention_days > 0, "log_retention_days must be positive"),
    ]
    
    for is_valid, error_message in validations:
        if not is_valid:
            raise ValueError(f"Invalid configuration: {error_message}")
    
    return True

# Example usage
if __name__ == "__main__":
    # Test configuration loading
    config = get_security_config()
    print(f"Loaded security config: {config}")
    
    # Test environment-specific config
    prod_config = get_environment_config('production')
    print(f"Production config: {prod_config}")
    
    # Validate configuration
    try:
        validate_config(config)
        print("Configuration is valid")
    except ValueError as e:
        print(f"Configuration error: {e}")