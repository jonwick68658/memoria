#!/bin/bash
# Memoria AI Upgrade Script
# Safe and reliable upgrade process with rollback capability

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="memoria-ai"
BACKUP_DIR="${BACKUP_DIR:-./backups/pre-upgrade}"
UPGRADE_LOG="${UPGRADE_LOG:-./logs/upgrade.log}"
ROLLBACK_ENABLED="${ROLLBACK_ENABLED:-true}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-300}"
BACKUP_TIMEOUT="${BACKUP_TIMEOUT:-600}"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
SKIP_TESTS="${SKIP_TESTS:-false}"
SKIP_BACKUP="${SKIP_BACKUP:-false}"
FORCE_UPGRADE="${FORCE_UPGRADE:-false}"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$UPGRADE_LOG"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$UPGRADE_LOG"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$UPGRADE_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$UPGRADE_LOG"
}

log_upgrade() {
    echo -e "${PURPLE}[UPGRADE]${NC} $1" | tee -a "$UPGRADE_LOG"
}

# Create log directory
create_log_dir() {
    local log_dir=$(dirname "$UPGRADE_LOG")
    if [ ! -d "$log_dir" ]; then
        mkdir -p "$log_dir"
    fi
}

# Pre-upgrade checks
pre_upgrade_checks() {
    log_upgrade "Running pre-upgrade checks..."
    
    # Check disk space
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 85 ]; then
        log_error "Insufficient disk space: ${disk_usage}% used"
        exit 1
    fi
    
    # Check memory
    local memory_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    if [ "$memory_usage" -gt 90 ]; then
        log_error "Insufficient memory: ${memory_usage}% used"
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker not found"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose >/dev/null 2>&1; then
        log_error "Docker Compose not found"
        exit 1
    fi
    
    # Check if services are running
    if ! docker-compose ps | grep -q "Up"; then
        log_error "Services are not running"
        exit 1
    fi
    
    log_success "Pre-upgrade checks passed"
}

# Create backup
create_backup() {
    if [ "$SKIP_BACKUP" = "true" ]; then
        log_warning "Backup skipped (SKIP_BACKUP=true)"
        return 0
    fi
    
    log_upgrade "Creating pre-upgrade backup..."
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    log_info "Backing up database..."
    timeout $BACKUP_TIMEOUT ./scripts/backup.sh --backup --output "$BACKUP_DIR/database_backup_$(date +%Y%m%d_%H%M%S).sql.gz"
    
    # Backup configuration
    log_info "Backing up configuration..."
    cp -r .env "$BACKUP_DIR/env_backup_$(date +%Y%m%d_%H%M%S)"
    cp -r docker-compose.yml "$BACKUP_DIR/docker-compose_backup_$(date +%Y%m%d_%H%M%S)"
    
    # Backup application data
    log_info "Backing up application data..."
    docker run --rm -v memoria_postgres_data:/data -v "$BACKUP_DIR:/backup" alpine tar czf /backup/postgres_data_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
    docker run --rm -v memoria_redis_data:/data -v "$BACKUP_DIR:/backup" alpine tar czf /backup/redis_data_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
    docker run --rm -v memoria_weaviate_data:/data -v "$BACKUP_DIR:/backup" alpine tar czf /backup/weaviate_data_backup_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .
    
    log_success "Backup created successfully"
}

# Pull new images
pull_images() {
    log_upgrade "Pulling new Docker images..."
    
    # Pull new images
    if [ -n "$DOCKER_REGISTRY" ]; then
        docker-compose pull --ignore-pull-failures
    else
        docker-compose pull
    fi
    
    log_success "Images pulled successfully"
}

# Run tests
run_tests() {
    if [ "$SKIP_TESTS" = "true" ]; then
        log_warning "Tests skipped (SKIP_TESTS=true)"
        return 0
    fi
    
    log_upgrade "Running tests..."
    
    # Run unit tests
    docker-compose run --rm memoria-api pytest tests/ -v
    
    # Run integration tests
    docker-compose run --rm memoria-api pytest tests/integration/ -v
    
    # Run health checks
    ./scripts/health-check.sh --once
    
    log_success "Tests passed"
}

# Stop services
stop_services() {
    log_upgrade "Stopping services..."
    
    # Graceful shutdown
    docker-compose stop
    
    # Wait for services to stop
    local timeout=60
    while docker-compose ps | grep -q "Up"; do
        sleep 1
        timeout=$((timeout - 1))
        if [ $timeout -eq 0 ]; then
            log_warning "Forcing services to stop..."
            docker-compose kill
            break
        fi
    done
    
    log_success "Services stopped"
}

# Update configuration
update_configuration() {
    log_upgrade "Updating configuration..."
    
    # Update environment variables
    if [ -f ".env.example" ]; then
        cp .env.example .env.new
        # Merge existing values with new ones
        while IFS='=' read -r key value; do
            if [[ $key =~ ^[A-Z_] ]]; then
                current_value=$(grep "^${key}=" .env | cut -d'=' -f2-)
                if [ -n "$current_value" ]; then
                    sed -i "s|^${key}=.*|${key}=${current_value}|" .env.new
                fi
            fi
        done < .env
        mv .env.new .env
    fi
    
    # Update Docker Compose
    if [ -f "docker-compose.yml.new" ]; then
        mv docker-compose.yml.new docker-compose.yml
    fi
    
    log_success "Configuration updated"
}

# Start services
start_services() {
    log_upgrade "Starting services..."
    
    # Start services
    docker-compose up -d
    
    # Wait for services to be ready
    local timeout=$HEALTH_CHECK_TIMEOUT
    while ! ./scripts/health-check.sh --once >/dev/null 2>&1; do
        sleep 5
        timeout=$((timeout - 5))
        if [ $timeout -eq 0 ]; then
            log_error "Services failed to start within timeout"
            return 1
        fi
    done
    
    log_success "Services started successfully"
}

# Post-upgrade checks
post_upgrade_checks() {
    log_upgrade "Running post-upgrade checks..."
    
    # Health check
    if ! ./scripts/health-check.sh --once; then
        log_error "Post-upgrade health check failed"
        return 1
    fi
    
    # API check
    local api_response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 http://localhost:8000/healthz)
    if [ "$api_response" != "200" ]; then
        log_error "API health check failed: $api_response"
        return 1
    fi
    
    # Database check
    local db_response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 30 http://localhost:8000/healthz/db)
    if [ "$db_response" != "200" ]; then
        log_error "Database health check failed: $db_response"
        return 1
    fi
    
    log_success "Post-upgrade checks passed"
}

# Rollback function
rollback() {
    if [ "$ROLLBACK_ENABLED" != "true" ]; then
        log_error "Rollback disabled (ROLLBACK_ENABLED=false)"
        return 1
    fi
    
    log_upgrade "Starting rollback..."
    
    # Stop services
    docker-compose stop
    
    # Restore database
    local latest_backup=$(ls -t "$BACKUP_DIR"/database_backup_*.sql.gz | head -1)
    if [ -n "$latest_backup" ]; then
        log_info "Restoring database from backup..."
        gunzip < "$latest_backup" | docker exec -i memoria-postgres-1 psql -U memoria -d memoria_db
    fi
    
    # Restore configuration
    local latest_env=$(ls -t "$BACKUP_DIR"/env_backup_* | head -1)
    if [ -n "$latest_env" ]; then
        cp "$latest_env" .env
    fi
    
    local latest_compose=$(ls -t "$BACKUP_DIR"/docker-compose_backup_* | head -1)
    if [ -n "$latest_compose" ]; then
        cp "$latest_compose" docker-compose.yml
    fi
    
    # Restore data volumes
    local postgres_backup=$(ls -t "$BACKUP_DIR"/postgres_data_backup_*.tar.gz | head -1)
    if [ -n "$postgres_backup" ]; then
        docker run --rm -v memoria_postgres_data:/data -v "$BACKUP_DIR:/backup" alpine tar xzf /backup/$(basename "$postgres_backup") -C /data
    fi
    
    local redis_backup=$(ls -t "$BACKUP_DIR"/redis_data_backup_*.tar.gz | head -1)
    if [ -n "$redis_backup" ]; then
        docker run --rm -v memoria_redis_data:/data -v "$BACKUP_DIR:/backup" alpine tar xzf /backup/$(basename "$redis_backup") -C /data
    fi
    
    local weaviate_backup=$(ls -t "$BACKUP_DIR"/weaviate_data_backup_*.tar.gz | head -1)
    if [ -n "$weaviate_backup" ]; then
        docker run --rm -v memoria_weaviate_data:/data -v "$BACKUP_DIR:/backup" alpine tar xzf /backup/$(basename "$weaviate_backup") -C /data
    fi
    
    # Start services
    docker-compose up -d
    
    log_success "Rollback completed"
}

# Generate upgrade report
generate_upgrade_report() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local report_file="upgrade_report_$(date +%Y%m%d_%H%M%S).json"
    
    # Collect system information
    local disk_usage=$(df -h / | awk 'NR==2 {print $5}')
    local memory_usage=$(free -h | awk 'NR==2{printf "%s/%s", $3,$2}')
    local cpu_cores=$(nproc)
    local load_average=$(uptime | awk -F'load average:' '{print $2}')
    
    # Container information
    local total_containers=$(docker ps -q | wc -l)
    local running_containers=$(docker ps --format "{{.Names}}" | wc -l)
    
    # Image information
    local image_info=$(docker images --format "{{.Repository}}:{{.Tag}} ({{.Size}})")
    
    # Generate report
    cat > "$report_file" << EOF
{
    "timestamp": "$timestamp",
    "upgrade_status": "success",
    "system": {
        "disk_usage": "$disk_usage",
        "memory_usage": "$memory_usage",
        "cpu_cores": $cpu_cores,
        "load_average": "$load_average"
    },
    "containers": {
        "total": $total_containers,
        "running": $running_containers
    },
    "images": {
        "details": "$image_info"
    },
    "backup_location": "$BACKUP_DIR",
    "rollback_enabled": $ROLLBACK_ENABLED
}
EOF
    
    log_success "Upgrade report generated: $report_file"
}

# Main upgrade process
upgrade() {
    log_upgrade "Starting upgrade process..."
    
    # Pre-upgrade checks
    pre_upgrade_checks
    
    # Create backup
    create_backup
    
    # Pull new images
    pull_images
    
    # Run tests
    run_tests
    
    # Stop services
    stop_services
    
    # Update configuration
    update_configuration
    
    # Start services
    if ! start_services; then
        log_error "Failed to start services"
        if [ "$ROLLBACK_ENABLED" = "true" ]; then
            rollback
        fi
        exit 1
    fi
    
    # Post-upgrade checks
    if ! post_upgrade_checks; then
        log_error "Post-upgrade checks failed"
        if [ "$ROLLBACK_ENABLED" = "true" ]; then
            rollback
        fi
        exit 1
    fi
    
    # Generate report
    generate_upgrade_report
    
    log_success "Upgrade completed successfully"
}

# Main function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Memoria AI Upgrade                        ║"
    echo "║              Safe and Reliable Upgrade Process               ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # Create log directory
    create_log_dir
    
    case "${1:-}" in
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --help, -h         Show this help message"
            echo "  --upgrade          Run full upgrade process"
            echo "  --rollback         Rollback to previous version"
            echo "  --check            Run pre-upgrade checks"
            echo "  --backup           Create backup only"
            echo "  --test             Run tests only"
            echo "  --report           Generate upgrade report"
            echo ""
            echo "Environment variables:"
            echo "  BACKUP_DIR         Backup directory (default: ./backups/pre-upgrade)"
            echo "  UPGRADE_LOG        Upgrade log file (default: ./logs/upgrade.log)"
            echo "  ROLLBACK_ENABLED   Enable rollback (default: true)"
            echo "  HEALTH_CHECK_TIMEOUT Health check timeout (default: 300)"
            echo "  BACKUP_TIMEOUT     Backup timeout (default: 600)"
            echo "  DOCKER_REGISTRY    Docker registry URL"
            echo "  IMAGE_TAG          Image tag (default: latest)"
            echo "  SKIP_TESTS         Skip tests (default: false)"
            echo "  SKIP_BACKUP        Skip backup (default: false)"
            echo "  FORCE_UPGRADE      Force upgrade (default: false)"
            exit 0
            ;;
        --upgrade)
            upgrade
            ;;
        --rollback)
            rollback
            ;;
        --check)
            pre_upgrade_checks
            ;;
        --backup)
            create_backup
            ;;
        --test)
            run_tests
            ;;
        --report)
            generate_upgrade_report
            ;;
        *)
            upgrade
            ;;
    esac
}

# Handle script arguments
main "$@"