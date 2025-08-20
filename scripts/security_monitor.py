#!/usr/bin/env python3
"""
Security Monitoring Script for Memoria
Provides real-time security monitoring and alerting capabilities
"""

import os
import sys
import time
import json
import logging
import argparse
import signal
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading
import queue
import subprocess

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.memoria.security.security_pipeline import SecurityPipeline
from src.memoria.security.threat_database import ThreatDatabase
from src.memoria.security.security_config import SecurityConfig

class SecurityMonitor:
    """Real-time security monitoring system"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = SecurityConfig(config_path)
        self.pipeline = SecurityPipeline()
        self.threat_db = ThreatDatabase()
        self.running = False
        self.alert_queue = queue.Queue()
        self.metrics = {
            'requests_processed': 0,
            'threats_detected': 0,
            'false_positives': 0,
            'alerts_sent': 0,
            'start_time': datetime.now()
        }
        
        # Setup logging
        self.setup_logging()
        
        # Load monitoring configuration
        self.monitoring_config = self.load_monitoring_config()
        
    def setup_logging(self):
        """Configure logging for security monitoring"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        log_level = getattr(logging, self.config.log_level.upper())
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(log_format))
        
        # File handler
        log_file = self.config.log_file or 'logs/security_monitor.log'
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(log_format))
        
        # Root logger
        self.logger = logging.getLogger('SecurityMonitor')
        self.logger.setLevel(log_level)
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        
    def load_monitoring_config(self) -> Dict[str, Any]:
        """Load monitoring configuration"""
        config_file = project_root / 'config' / 'monitoring.json'
        if config_file.exists():
            with open(config_file) as f:
                return json.load(f)
        return {
            'check_interval': 60,
            'alert_threshold': 0.8,
            'email_alerts': False,
            'webhook_alerts': True,
            'webhook_url': 'http://localhost:8080/security/alerts',
            'metrics_retention_days': 30
        }
        
    def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health"""
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'components': {},
            'metrics': self.metrics.copy()
        }
        
        # Check security pipeline
        try:
            test_result = self.pipeline.validate_input("test", "test")
            health_status['components']['security_pipeline'] = {
                'status': 'healthy',
                'response_time': test_result.processing_time
            }
        except Exception as e:
            health_status['components']['security_pipeline'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
            
        # Check threat database
        try:
            signatures = self.threat_db.get_all_signatures()
            health_status['components']['threat_database'] = {
                'status': 'healthy',
                'signatures_count': len(signatures),
                'last_update': self.threat_db.get_last_update()
            }
        except Exception as e:
            health_status['components']['threat_database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_status['status'] = 'degraded'
            
        # Check disk space
        try:
            disk_usage = subprocess.check_output(['df', str(project_root)]).decode().split('\n')[1]
            disk_percent = int(disk_usage.split()[4].replace('%', ''))
            health_status['components']['disk_space'] = {
                'status': 'healthy' if disk_percent < 80 else 'warning',
                'usage_percent': disk_percent
            }
        except Exception as e:
            health_status['components']['disk_space'] = {
                'status': 'unknown',
                'error': str(e)
            }
            
        return health_status
        
    def monitor_security_events(self):
        """Monitor security events in real-time"""
        self.logger.info("Starting security event monitoring...")
        
        # Monitor log files
        log_files = [
            'logs/security.log',
            'logs/application.log',
            'logs/error.log'
        ]
        
        for log_file in log_files:
            log_path = project_root / log_file
            if log_path.exists():
                threading.Thread(
                    target=self.monitor_log_file,
                    args=(log_path,),
                    daemon=True
                ).start()
                
    def monitor_log_file(self, log_path: Path):
        """Monitor a specific log file for security events"""
        self.logger.info(f"Monitoring log file: {log_path}")
        
        try:
            with open(log_path, 'r') as f:
                # Go to end of file
                f.seek(0, 2)
                
                while self.running:
                    line = f.readline()
                    if line:
                        self.process_log_line(line, log_path)
                    else:
                        time.sleep(1)
                        
        except Exception as e:
            self.logger.error(f"Error monitoring {log_path}: {e}")
            
    def process_log_line(self, line: str, log_path: Path):
        """Process a single log line for security events"""
        # Look for security-related patterns
        security_patterns = [
            'THREAT_DETECTED',
            'PROMPT_INJECTION',
            'SQL_INJECTION',
            'XSS_ATTACK',
            'RATE_LIMIT_EXCEEDED',
            'VALIDATION_ERROR',
            'UNAUTHORIZED_ACCESS'
        ]
        
        for pattern in security_patterns:
            if pattern in line.upper():
                self.handle_security_event({
                    'type': pattern,
                    'message': line.strip(),
                    'source': str(log_path),
                    'timestamp': datetime.now().isoformat()
                })
                
    def handle_security_event(self, event: Dict[str, Any]):
        """Handle detected security events"""
        self.logger.warning(f"Security event detected: {event['type']}")
        
        # Update metrics
        self.metrics['threats_detected'] += 1
        
        # Add to alert queue
        self.alert_queue.put(event)
        
        # Check if alert threshold is reached
        if self.should_send_alert(event):
            self.send_alert(event)
            
    def should_send_alert(self, event: Dict[str, Any]) -> bool:
        """Determine if an alert should be sent"""
        # Check alert threshold
        if self.metrics['threats_detected'] > self.monitoring_config['alert_threshold']:
            return True
            
        # Check for critical events
        critical_events = ['PROMPT_INJECTION', 'SQL_INJECTION', 'UNAUTHORIZED_ACCESS']
        if any(event in event['type'] for event in critical_events):
            return True
            
        return False
        
    def send_alert(self, event: Dict[str, Any]):
        """Send security alert"""
        self.logger.info(f"Sending security alert: {event['type']}")
        
        # Send webhook alert
        if self.monitoring_config.get('webhook_alerts'):
            self.send_webhook_alert(event)
            
        # Send email alert (placeholder)
        if self.monitoring_config.get('email_alerts'):
            self.send_email_alert(event)
            
        self.metrics['alerts_sent'] += 1
        
    def send_webhook_alert(self, event: Dict[str, Any]):
        """Send webhook alert"""
        try:
            import requests
            webhook_url = self.monitoring_config['webhook_url']
            response = requests.post(webhook_url, json=event, timeout=5)
            response.raise_for_status()
            self.logger.info("Webhook alert sent successfully")
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}")
            
    def send_email_alert(self, event: Dict[str, Any]):
        """Send email alert (placeholder)"""
        self.logger.info("Email alert would be sent here")
        
    def generate_security_report(self) -> Dict[str, Any]:
        """Generate comprehensive security report"""
        uptime = datetime.now() - self.metrics['start_time']
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'uptime': str(uptime),
            'metrics': self.metrics,
            'health_status': self.check_system_health(),
            'recent_alerts': []
        }
        
        # Get recent alerts
        alerts = []
        while not self.alert_queue.empty():
            try:
                alerts.append(self.alert_queue.get_nowait())
            except queue.Empty:
                break
                
        report['recent_alerts'] = alerts[-10:]  # Last 10 alerts
        
        return report
        
    def save_report(self, report: Dict[str, Any]):
        """Save security report to file"""
        report_file = project_root / 'logs' / f'security_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        self.logger.info(f"Security report saved: {report_file}")
        
    def start_monitoring(self):
        """Start security monitoring"""
        self.logger.info("Starting security monitoring...")
        self.running = True
        
        # Start monitoring threads
        self.monitor_security_events()
        
        # Main monitoring loop
        try:
            while self.running:
                # Check system health
                health = self.check_system_health()
                if health['status'] != 'healthy':
                    self.logger.warning(f"System health: {health['status']}")
                    
                # Generate periodic reports
                if datetime.now().minute == 0:  # Every hour
                    report = self.generate_security_report()
                    self.save_report(report)
                    
                time.sleep(self.monitoring_config['check_interval'])
                
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        except Exception as e:
            self.logger.error(f"Monitoring error: {e}")
        finally:
            self.stop_monitoring()
            
    def stop_monitoring(self):
        """Stop security monitoring"""
        self.logger.info("Stopping security monitoring...")
        self.running = False
        
        # Save final report
        report = self.generate_security_report()
        self.save_report(report)
        
        self.logger.info("Security monitoring stopped")
        
    def status(self):
        """Get current monitoring status"""
        uptime = datetime.now() - self.metrics['start_time']
        health = self.check_system_health()
        
        print("\n" + "="*50)
        print("Memoria Security Monitor Status")
        print("="*50)
        print(f"Status: {'Running' if self.running else 'Stopped'}")
        print(f"Uptime: {uptime}")
        print(f"Requests Processed: {self.metrics['requests_processed']}")
        print(f"Threats Detected: {self.metrics['threats_detected']}")
        print(f"Alerts Sent: {self.metrics['alerts_sent']}")
        print(f"System Health: {health['status']}")
        print("="*50)
        
        # Component status
        print("\nComponent Status:")
        for component, status in health['components'].items():
            status_icon = "✅" if status['status'] == 'healthy' else "❌"
            print(f"  {status_icon} {component}: {status['status']}")
            
    def test_alert_system(self):
        """Test the alert system"""
        test_event = {
            'type': 'TEST_ALERT',
            'message': 'This is a test security alert',
            'source': 'security_monitor.py',
            'timestamp': datetime.now().isoformat()
        }
        
        self.logger.info("Testing alert system...")
        self.handle_security_event(test_event)
        print("✅ Alert system test completed")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("\nReceived shutdown signal...")
    if monitor:
        monitor.stop_monitoring()
    sys.exit(0)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Memoria Security Monitor')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--status', action='store_true', help='Show current status')
    parser.add_argument('--test-alerts', action='store_true', help='Test alert system')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    
    args = parser.parse_args()
    
    global monitor
    monitor = SecurityMonitor(args.config)
    
    # Handle signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if args.status:
        monitor.status()
    elif args.test_alerts:
        monitor.test_alert_system()
    elif args.daemon:
        # Daemon mode (background)
        import daemon
        with daemon.DaemonContext():
            monitor.start_monitoring()
    else:
        # Interactive mode
        monitor.start_monitoring()

if __name__ == '__main__':
    main()