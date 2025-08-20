#!/bin/bash
# Secure Deployment Script for Memoria
# This script deploys Memoria with enterprise-grade security features

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_DIR="${PROJECT_ROOT}/config"
LOGS_DIR="${PROJECT_ROOT}/logs"
SECURITY_DIR="${PROJECT_ROOT}/security"
BACKUP_DIR="${PROJECT_ROOT}/backups"

# Logging
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
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
    log "Python version: $PYTHON_VERSION"
    
    # Check required Python packages
    local required_packages=("fastapi" "uvicorn" "pydantic" "cryptography" "redis")
    for package in "${required_packages[@]}"; do
        if ! python3 -c "import $package" 2>/dev/null; then
            error "Required package '$package' is not installed"
            exit 1
        fi
    done
    
    # Check Docker (optional)
    if command -v docker &> /dev/null; then
        log "Docker is available"
    else
        warn "Docker is not available - container deployment disabled"
    fi
    
    log "Prerequisites check completed"
}

# Setup directories
setup_directories() {
    log "Setting up directories..."
    
    mkdir -p "$CONFIG_DIR" "$LOGS_DIR" "$SECURITY_DIR" "$BACKUP_DIR"
    mkdir -p "$LOGS_DIR/security" "$LOGS_DIR/audit" "$LOGS_DIR/app"
    
    # Set proper permissions
    chmod 750 "$CONFIG_DIR" "$SECURITY_DIR"
    chmod 755 "$LOGS_DIR"
    
    log "Directories setup completed"
}

# Generate security keys
generate_security_keys() {
    log "Generating security keys..."
    
    local key_file="${SECURITY_DIR}/.security_keys"
    
    if [[ ! -f "$key_file" ]]; then
        log "Generating new security keys..."
        
        # Generate encryption key
        local encryption_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
        
        # Generate JWT secret
        local jwt_secret=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        
        # Generate API keys
        local api_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        
        # Save keys securely
        cat > "$key_file" << EOF
# Memoria Security Keys
# Generated on $(date)
# KEEP THIS FILE SECURE!

ENCRYPTION_KEY=$encryption_key
JWT_SECRET=$jwt_secret
API_KEY=$api_key
EOF
        
        chmod 600 "$key_file"
        log "Security keys generated and saved to $key_file"
    else
        log "Security keys already exist"
    fi
    
    # Source the keys
    source "$key_file"
    export ENCRYPTION_KEY JWT_SECRET API_KEY
}

# Configure security settings
configure_security() {
    log "Configuring security settings..."
    
    # Copy security configuration if it doesn't exist
    if [[ ! -f "${CONFIG_DIR}/security.json" ]]; then
        log "Creating security configuration..."
        cp "${CONFIG_DIR}/security.json.example" "${CONFIG_DIR}/security.json"
    fi
    
    # Validate security configuration
    if python3 -c "
import json
try:
    with open('${CONFIG_DIR}/security.json') as f:
        config = json.load(f)
    print('Security configuration is valid')
except Exception as e:
    print(f'Invalid security configuration: {e}')
    exit(1)
"; then
        log "Security configuration validated"
    else
        error "Invalid security configuration"
        exit 1
    fi
    
    # Set secure file permissions
    chmod 640 "${CONFIG_DIR}/security.json"
    
    log "Security configuration completed"
}

# Initialize threat database
initialize_threat_db() {
    log "Initializing threat database..."
    
    python3 -c "
from src.memoria.security.threat_database import ThreatDatabase
db = ThreatDatabase()
db.initialize_database()
print('Threat database initialized')
"
    
    log "Threat database initialization completed"
}

# Run security tests
run_security_tests() {
    log "Running security tests..."
    
    # Run unit tests
    if python3 -m pytest tests/test_security_system.py -v --tb=short; then
        log "Security tests passed"
    else
        error "Security tests failed"
        exit 1
    fi
    
    # Run security scan
    if command -v bandit &> /dev/null; then
        log "Running security scan..."
        bandit -r src/memoria/security/ -f json -o "${LOGS_DIR}/security_scan.json"
        log "Security scan completed"
    fi
    
    log "Security testing completed"
}

# Setup monitoring
setup_monitoring() {
    log "Setting up security monitoring..."
    
    # Create monitoring configuration
    cat > "${CONFIG_DIR}/monitoring.json" << EOF
{
  "check_interval": 60,
  "alert_threshold": 0.8,
  "email_alerts": false,
  "webhook_alerts": true,
  "webhook_url": "http://localhost:8080/security/alerts",
  "metrics_retention_days": 30
}
EOF
    
    # Create systemd service for monitoring (if systemd is available)
    if command -v systemctl &> /dev/null; then
        log "Creating systemd service for security monitoring..."
        
        cat > "/etc/systemd/system/memoria-security.service" << EOF
[Unit]
Description=Memoria Security Monitor
After=network.target

[Service]
Type=simple
User=memoria
Group=memoria
WorkingDirectory=${PROJECT_ROOT}
ExecStart=${PROJECT_ROOT}/venv/bin/python scripts/security_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        systemctl daemon-reload
        log "Systemd service created"
    fi
    
    log "Security monitoring setup completed"
}

# Backup security configuration
backup_security_config() {
    log "Creating security configuration backup..."
    
    local backup_file="${BACKUP_DIR}/security_config_$(date +%Y%m%d_%H%M%S).tar.gz"
    
    tar -czf "$backup_file" \
        -C "$PROJECT_ROOT" \
        config/security.json \
        security/ \
        logs/security/ \
        2>/dev/null || true
    
    log "Security configuration backed up to $backup_file"
}

# Deploy application
deploy_application() {
    log "Deploying Memoria application..."
    
    # Set environment variables
    export SECURITY_ENABLED=true
    export SECURITY_LOG_LEVEL=INFO
    export SECURITY_THREAT_THRESHOLD=0.7
    
    # Start application with security
    log "Starting Memoria with security features..."
    
    # Create startup script
    cat > "${PROJECT_ROOT}/start_secure.sh" << EOF
#!/bin/bash
# Secure startup script for Memoria

set -euo pipefail

# Source security keys
source ${SECURITY_DIR}/.security_keys

# Start security monitoring in background
python3 scripts/security_monitor.py --daemon &

# Wait for security monitoring to start
sleep 5

# Start main application
python3 -m uvicorn app.main:app \\
    --host 0.0.0.0 \\
    --port 8080 \\
    --workers 4 \\
    --ssl-keyfile ${SECURITY_DIR}/server.key \\
    --ssl-certfile ${SECURITY_DIR}/server.crt \\
    --log-level info

EOF
    
    chmod +x "${PROJECT_ROOT}/start_secure.sh"
    
    log "Application deployment completed"
}

# Health check
health_check() {
    log "Performing health check..."
    
    # Check if security monitoring is running
    if pgrep -f "security_monitor.py" > /dev/null; then
        log "Security monitoring is running"
    else
        warn "Security monitoring is not running"
    fi
    
    # Check if application is responding
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health | grep -q "200"; then
        log "Application is responding"
    else
        warn "Application is not responding"
    fi
    
    log "Health check completed"
}

# Main deployment function
main() {
    log "Starting secure deployment of Memoria..."
    
    # Parse command line arguments
    local skip_tests=false
    local skip_backup=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-tests)
                skip_tests=true
                shift
                ;;
            --skip-backup)
                skip_backup=true
                shift
                ;;
            --help)
                echo "Usage: $0 [--skip-tests] [--skip-backup] [--help]"
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Execute deployment steps
    check_prerequisites
    setup_directories
    generate_security_keys
    configure_security
    initialize_threat_db
    
    if [[ "$skip_tests" != true ]]; then
        run_security_tests
    fi
    
    if [[ "$skip_backup" != true ]]; then
        backup_security_config
    fi
    
    setup_monitoring
    deploy_application
    health_check
    
    log "Secure deployment completed successfully!"
    log "Access your secure Memoria instance at: https://localhost:8080"
    log "Security dashboard: https://localhost:8080/security/dashboard"
}

# Execute main function
main "$@"