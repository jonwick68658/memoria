"""Security monitoring and alerting system for Memoria."""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import threading
import queue
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from .security_config import get_security_config
from .threat_database import ThreatDatabase

@dataclass
class SecurityAlert:
    """Security alert data structure."""
    timestamp: datetime
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    alert_type: str
    message: str
    details: Dict[str, Any]
    source_ip: Optional[str] = None
    user_id: Optional[str] = None

class SecurityMonitor:
    """Real-time security monitoring system."""
    
    def __init__(self):
        self.config = get_security_config()
        self.logger = logging.getLogger('security.monitor')
        self.threat_db = ThreatDatabase()
        self.alert_queue = queue.Queue()
        self.is_running = False
        self.monitor_thread = None
        
        # Alert thresholds
        self.alert_thresholds = {
            'CRITICAL': 0.9,
            'HIGH': 0.8,
            'MEDIUM': 0.7,
            'LOW': 0.5
        }
        
        # Initialize handlers
        self._setup_logging()
        self._setup_handlers()
    
    def _setup_logging(self):
        """Configure security logging."""
        if not self.config.enable_security_logging:
            return
            
        # Create logs directory if it doesn't exist
        log_dir = Path(self.config.log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure rotating file handler
        from logging.handlers import RotatingFileHandler
        
        handler = RotatingFileHandler(
            self.config.log_file,
            maxBytes=self.config.max_log_size_mb * 1024 * 1024,
            backupCount=5
        )
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        self.logger.addHandler(handler)
        self.logger.setLevel(getattr(logging, self.config.log_level))
    
    def _setup_handlers(self):
        """Setup alert handlers."""
        self.handlers = {
            'log': self._handle_log_alert,
            'email': self._handle_email_alert,
            'webhook': self._handle_webhook_alert
        }
    
    def start_monitoring(self):
        """Start security monitoring."""
        if self.is_running:
            return
            
        self.is_running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitor_thread.start()
        self.logger.info("Security monitoring started")
    
    def stop_monitoring(self):
        """Stop security monitoring."""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        self.logger.info("Security monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.is_running:
            try:
                self._check_security_health()
                self._process_alerts()
                time.sleep(self.config.health_check_interval)
            except Exception as e:
                self.logger.error(f"Monitoring error: {e}")
                time.sleep(60)  # Wait before retrying
    
    def _check_security_health(self):
        """Check overall security health."""
        # Check log file size
        log_file = Path(self.config.log_file)
        if log_file.exists():
            size_mb = log_file.stat().st_size / (1024 * 1024)
            if size_mb > self.config.max_log_size_mb * 0.9:
                self._create_alert(
                    severity='HIGH',
                    alert_type='LOG_SIZE_WARNING',
                    message=f"Security log file approaching size limit: {size_mb:.1f}MB",
                    details={'current_size_mb': size_mb, 'limit_mb': self.config.max_log_size_mb}
                )
    
    def _process_alerts(self):
        """Process queued alerts."""
        while not self.alert_queue.empty():
            try:
                alert = self.alert_queue.get_nowait()
                self._handle_alert(alert)
            except queue.Empty:
                break
    
    def _create_alert(self, severity: str, alert_type: str, message: str, 
                     details: Dict[str, Any], source_ip: Optional[str] = None,
                     user_id: Optional[str] = None):
        """Create a security alert."""
        alert = SecurityAlert(
            timestamp=datetime.now(),
            severity=severity,
            alert_type=alert_type,
            message=message,
            details=details,
            source_ip=source_ip,
            user_id=user_id
        )
        
        self.alert_queue.put(alert)
        self.logger.warning(f"Security alert: {severity} - {message}")
    
    def _handle_alert(self, alert: SecurityAlert):
        """Handle security alert."""
        for handler_name, handler_func in self.handlers.items():
            try:
                handler_func(alert)
            except Exception as e:
                self.logger.error(f"Handler {handler_name} failed: {e}")
    
    def _handle_log_alert(self, alert: SecurityAlert):
        """Log security alert."""
        log_entry = {
            'timestamp': alert.timestamp.isoformat(),
            'severity': alert.severity,
            'type': alert.alert_type,
            'message': alert.message,
            'details': alert.details,
            'source_ip': alert.source_ip,
            'user_id': alert.user_id
        }
        
        self.logger.critical(json.dumps(log_entry))
    
    def _handle_email_alert(self, alert: SecurityAlert):
        """Send email alert (placeholder)."""
        # This would integrate with actual email service
        self.logger.info(f"Email alert would be sent: {alert.message}")
    
    def _handle_webhook_alert(self, alert: SecurityAlert):
        """Send webhook alert (placeholder)."""
        # This would integrate with actual webhook service
        self.logger.info(f"Webhook alert would be sent: {alert.message}")
    
    def report_security_event(self, event_type: str, details: Dict[str, Any],
                            severity: str = 'MEDIUM', source_ip: Optional[str] = None,
                            user_id: Optional[str] = None):
        """Report a security event."""
        self._create_alert(
            severity=severity,
            alert_type=event_type,
            message=f"Security event: {event_type}",
            details=details,
            source_ip=source_ip,
            user_id=user_id
        )
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """Get current security metrics."""
        return {
            'timestamp': datetime.now().isoformat(),
            'threat_signatures': len(self.threat_db.get_all_signatures()),
            'monitoring_status': 'active' if self.is_running else 'inactive',
            'config': {
                'max_input_length': self.config.max_input_length,
                'threat_score_threshold': self.config.threat_score_threshold,
                'max_requests_per_minute': self.config.max_requests_per_minute
            }
        }
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent security alerts."""
        # This would typically query a database
        # For now, return empty list
        return []

class SecurityMetricsCollector:
    """Collect security metrics for monitoring."""
    
    def __init__(self):
        self.config = get_security_config()
        self.logger = logging.getLogger('security.metrics')
        self.metrics = {
            'security_events_total': 0,
            'threats_detected_total': 0,
            'blocked_requests_total': 0,
            'validation_failures_total': 0,
            'system_errors_total': 0
        }
    
    def increment_metric(self, metric_name: str, value: int = 1):
        """Increment a security metric."""
        if metric_name in self.metrics:
            self.metrics[metric_name] += value
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all security metrics."""
        return {
            'timestamp': datetime.now().isoformat(),
            'metrics': self.metrics.copy()
        }
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        output = []
        for metric_name, value in self.metrics.items():
            output.append(f"{metric_name} {value}")
        return "\n".join(output)

# Global instances
_monitor = None
_metrics = None

def get_security_monitor() -> SecurityMonitor:
    """Get the global security monitor."""
    global _monitor
    if _monitor is None:
        _monitor = SecurityMonitor()
    return _monitor

def get_metrics_collector() -> SecurityMetricsCollector:
    """Get the global metrics collector."""
    global _metrics
    if _metrics is None:
        _metrics = SecurityMetricsCollector()
    return _metrics

def start_security_monitoring():
    """Start global security monitoring."""
    monitor = get_security_monitor()
    monitor.start_monitoring()

def stop_security_monitoring():
    """Stop global security monitoring."""
    monitor = get_security_monitor()
    monitor.stop_monitoring()