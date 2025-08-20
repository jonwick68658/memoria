#!/bin/bash
# Enterprise Security Deployment Script for Memoria
# This script automates the complete security system deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECURITY_DIR="$PROJECT_ROOT/src/memoria/security"
LOGS_DIR="$PROJECT_ROOT/logs"
CONFIG_FILE="$PROJECT_ROOT/security_config.json"
VENV_DIR="$PROJECT_ROOT/venv"

# Logging
LOG_FILE="$LOGS_DIR/security_deployment.log"
mkdir -p "$LOGS_DIR"

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}" | tee -a "$LOG_FILE"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is required but not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    info "Python version: $PYTHON_VERSION"
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        error "pip3 is required but not installed"
        exit 1
    fi
    
    # Check virtual environment
    if [[ ! -d "$VENV_DIR" ]]; then
        warning "Virtual environment not found, creating..."
        python3 -m venv "$VENV_DIR"
    fi
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Check required packages
    pip3 install -r "$PROJECT_ROOT/requirements.txt" --quiet
    
    log "Prerequisites check completed"
}

# Create directory structure
create_directories() {
    log "Creating directory structure..."
    
    directories=(
        "$SECURITY_DIR"
        "$LOGS_DIR"
        "$PROJECT_ROOT/config"
        "$PROJECT_ROOT/data/security"
        "$PROJECT_ROOT/backups"
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
        info "Created directory: $dir"
    done
    
    log "Directory structure created"
}

# Install security dependencies
install_dependencies() {
    log "Installing security dependencies..."
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Security-specific packages
    security_packages=(
        "cryptography>=3.4.8"
        "bandit>=1.7.0"
        "safety>=2.0.0"
        "semgrep>=0.100.0"
        "prometheus-client>=0.14.0"
        "redis>=4.0.0"
    )
    
    for package in "${security_packages[@]}"; do
        info "Installing $package..."
        pip3 install "$package" --quiet
    done
    
    log "Security dependencies installed"
}

# Generate security configuration
generate_config() {
    log "Generating security configuration..."
    
    # Create default configuration
    cat > "$CONFIG_FILE" << EOF
{
  "max_input_length": 10000,
  "max_tokens_per_request": 4000,
  "threat_score_threshold": 0.7,
  "similarity_threshold": 0.85,
  "enable_rate_limiting": true,
  "requests_per_minute": 60,
  "enable_monitoring": true,
  "log_level": "INFO",
  "log_file": "logs/security.log",
  "enable_alerts": true,
  "alert_threshold": 0.9,
  "enable_caching": true,
  "async_processing": true,
  "max_concurrent_requests": 100
}
EOF
    
    info "Security configuration generated: $CONFIG_FILE"
}

# Initialize threat database
init_threat_database() {
    log "Initializing threat database..."
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Run threat database initialization
    python3 -c "
from src.memoria.security.threat_database import ThreatDatabase
db = ThreatDatabase()
db.initialize_database()
print('Threat database initialized with', len(db.get_all_signatures()), 'signatures')
"
    
    log "Threat database initialized"
}

# Run security tests
run_security_tests() {
    log "Running security tests..."
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Run comprehensive tests
    python3 -m pytest tests/test_security_system.py -v --tb=short
    
    # Run static analysis
    info "Running static analysis..."
    bandit -r src/memoria/security/ -f json -o "$LOGS_DIR/bandit_report.json"
    
    # Run dependency check
    info "Checking dependencies..."
    safety check --json --output "$LOGS_DIR/safety_report.json"
    
    log "Security tests completed"
}

# Setup monitoring
setup_monitoring() {
    log "Setting up security monitoring..."
    
    # Create systemd service for monitoring
    cat > /tmp/memoria-security.service << EOF
[Unit]
Description=Memoria Security Monitor
After=network.target

[Service]
Type=simple
User=memoria
WorkingDirectory=$PROJECT_ROOT
Environment=PYTHONPATH=$PROJECT_ROOT
ExecStart=$VENV_DIR/bin/python scripts/security_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    # Install service (requires sudo)
    if [[ $EUID -eq 0 ]]; then
        cp /tmp/memoria-security.service /etc/systemd/system/
        systemctl daemon-reload
        systemctl enable memoria-security
        info "Security monitoring service installed"
    else
        warning "Run as root to install systemd service"
    fi
    
    # Create log rotation
    cat > /tmp/memoria-security << EOF
$LOGS_DIR/security.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 memoria memoria
    postrotate
        systemctl reload memoria-security || true
    endscript
}
EOF
    
    if [[ $EUID -eq 0 ]]; then
        cp /tmp/memoria-security /etc/logrotate.d/
        info "Log rotation configured"
    fi
    
    log "Monitoring setup completed"
}

# Harden system
harden_system() {
    log "Hardening system security..."
    
    # Set file permissions
    chmod 750 "$SECURITY_DIR"
    chmod 640 "$CONFIG_FILE"
    chmod 750 "$LOGS_DIR"
    
    # Create security user (if running as root)
    if [[ $EUID -eq 0 ]]; then
        useradd -r -s /bin/false memoria 2>/dev/null || true
        chown -R memoria:memoria "$PROJECT_ROOT"
        info "Security user created"
    fi
    
    # Create firewall rules (if ufw available)
    if command -v ufw &> /dev/null; then
        ufw allow 22/tcp
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw --force enable
        info "Firewall configured"
    fi
    
    log "System hardening completed"
}

# Generate security report
generate_security_report() {
    log "Generating security report..."
    
    REPORT_FILE="$LOGS_DIR/security_deployment_report_$(date +%Y%m%d_%H%M%S).md"
    
    cat > "$REPORT_FILE" << EOF
# Memoria Security Deployment Report

**Date:** $(date)
**Environment:** ${ENVIRONMENT:-production}
**Version:** $(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

## Deployment Summary

### Components Installed
- Security pipeline
- Input validation
- Threat detection
- Rate limiting
- Monitoring system
- Audit logging

### Configuration
- Max input length: $(grep max_input_length "$CONFIG_FILE" | cut -d':' -f2 | tr -d ' ,')
- Threat threshold: $(grep threat_score_threshold "$CONFIG_FILE" | cut -d':' -f2 | tr -d ' ,')
- Rate limiting: $(grep enable_rate_limiting "$CONFIG_FILE" | cut -d':' -f2 | tr -d ' ,')

### Security Tests
- Unit tests: $(python3 -m pytest tests/test_security_system.py --collect-only | grep -c "test_" || echo "0") tests
- Static analysis: $(test -f "$LOGS_DIR/bandit_report.json" && echo "completed" || echo "pending")
- Dependency check: $(test -f "$LOGS_DIR/safety_report.json" && echo "completed" || echo "pending")

### Next Steps
1. Review security logs in $LOGS_DIR
2. Configure monitoring alerts
3. Schedule regular security audits
4. Update threat signatures weekly

## Verification Commands
\`\`\`bash
# Check security status
python scripts/security_monitor.py --status

# Test security features
python scripts/test_security.sh

# View security logs
tail -f $LOGS_DIR/security.log
\`\`\`
EOF
    
    log "Security report generated: $REPORT_FILE"
}

# Main deployment function
main() {
    log "Starting Memoria Enterprise Security Deployment"
    log "Project root: $PROJECT_ROOT"
    
    # Parse command line arguments
    ENVIRONMENT="${1:-production}"
    info "Environment: $ENVIRONMENT"
    
    # Deployment steps
    check_prerequisites
    create_directories
    install_dependencies
    generate_config
    init_threat_database
    run_security_tests
    setup_monitoring
    harden_system
    generate_security_report
    
    log "✅ Enterprise security deployment completed successfully!"
    log "📊 Check the security report: $LOGS_DIR/security_deployment_report_*.md"
    log "🔍 Monitor security logs: tail -f $LOGS_DIR/security.log"
    log "🚀 Start the application: python app/main.py"
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [environment]"
        echo "Environments: development, staging, production"
        echo "Example: $0 production"
        exit 0
        ;;
    --version|-v)
        echo "Memoria Security Deployment Script v1.0"
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac