#!/bin/bash
# Memoria AI Restore Script
# Complete system restoration from backups

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
PROJECT_NAME="memoria"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RESTORE_LOG="${RESTORE_LOG:-./logs/restore.log}"
RESTORE_TIMEOUT="${RESTORE_TIMEOUT:-3600}"
FORCE_RESTORE="${FORCE_RESTORE:-false}"
SKIP_CONFIRMATION="${SKIP_CONFIRMATION:-false}"
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-300}"
BACKUP_DATE="${BACKUP_DATE:-}"
BACKUP_TYPE="${BACKUP_TYPE:-full}"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$RESTORE_LOG"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$RESTORE_LOG"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$RESTORE_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$RESTORE_LOG"
}

log_restore() {
    echo -e "${PURPLE}[RESTORE]${NC} $1" | tee -a "$RESTORE_LOG"
}

# Create log directory
create_log_dir() {
    local log_dir=$(dirname "$RESTORE_LOG")
    if [ ! -d "$log_dir" ]; then
        mkdir -p "$log_dir"
    fi
}

# List available backups
list_backups() {
    log_restore "Available backups:"
    
    echo -e "\n${CYAN}Database Backups:${NC}"
    find "$BACKUP_DIR" -name "database_backup_*.sql.gz" -type f -exec basename {} \; | sort -r | head -10
    
    echo -e "\n${CYAN}Full System Backups:${NC}"
    find "$BACKUP_DIR" -name "full_backup_*.tar.gz" -type f -exec basename {} \; | sort -r | head -10
    
    echo -e "\n${CYAN}Volume Backups:${NC}"
    find "$BACKUP_DIR" -name "*_data_backup_*.tar.gz" -type f -exec basename {} \; | sort -r | head -10
    
    echo -e "\n${CYAN}Configuration Backups:${NC}"
    find "$BACKUP_DIR" -name "config_backup_*.tar.gz" -type f -exec basename {} \; | sort -r | head -10
}

# Validate backup
validate_backup() {
    local backup_file="$1"
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    # Check file integrity
    if [[ "$backup_file" == *.gz ]]; then
        if ! gzip -t "$backup_file" 2>/dev/null; then
            log_error "Backup file is corrupted: $backup_file"
            return 1
        fi
    elif [[ "$backup_file" == *.tar.gz ]]; then
        if ! tar -tzf "$backup_file" >/dev/null 2>&1; then
            log_error "Backup file is corrupted: $backup_file"
            return 1
        fi
    fi
    
    log_success "Backup validation passed: $backup_file"
    return 0
}

# Pre-restore checks
pre_restore_checks() {
    log_restore "Running pre-restore checks..."
    
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
    
    log_success "Pre-restore checks passed"
}

# Stop services
stop_services() {
    log_restore "Stopping services..."
    
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
    
    # Remove containers
    docker-compose down
    
    log_success "Services stopped"
}

# Restore database
restore_database() {
    local backup_file="$1"
    
    log_restore "Restoring database..."
    
    # Validate backup
    if ! validate_backup "$backup_file"; then
        return 1
    fi
    
    # Stop database container
    docker-compose stop postgres
    
    # Remove existing database volume
    docker volume rm memoria_postgres_data 2>/dev/null || true
    
    # Create new volume
    docker volume create memoria_postgres_data
    
    # Start database container
    docker-compose up -d postgres
    
    # Wait for database to be ready
    local timeout=60
    while ! docker-compose exec postgres pg_isready -U memoria >/dev/null 2>&1; do
        sleep 1
        timeout=$((timeout - 1))
        if [ $timeout -eq 0 ]; then
            log_error "Database failed to start"
            return 1
        fi
    done
    
    # Restore database
    gunzip < "$backup_file" | docker exec -i memoria-postgres-1 psql -U memoria -d memoria_db
    
    log_success "Database restored successfully"
}

# Restore volumes
restore_volumes() {
    local backup_dir="$1"
    
    log_restore "Restoring volumes..."
    
    # Restore PostgreSQL data
    local postgres_backup=$(find "$backup_dir" -name "postgres_data_backup_*.tar.gz" -type f | sort -r | head -1)
    if [ -n "$postgres_backup" ] && validate_backup "$postgres_backup"; then
        log_info "Restoring PostgreSQL data..."
        docker volume rm memoria_postgres_data 2>/dev/null || true
        docker volume create memoria_postgres_data
        docker run --rm -v memoria_postgres_data:/data -v "$backup_dir:/backup" alpine tar xzf "/backup/$(basename "$postgres_backup")" -C /data
    fi
    
    # Restore Redis data
    local redis_backup=$(find "$backup_dir" -name "redis_data_backup_*.tar.gz" -type f | sort -r | head -1)
    if [ -n "$redis_backup" ] && validate_backup "$redis_backup"; then
        log_info "Restoring Redis data..."
        docker volume rm memoria_redis_data 2>/dev/null || true
        docker volume create memoria_redis_data
        docker run --rm -v memoria_redis_data:/data -v "$backup_dir:/backup" alpine tar xzf "/backup/$(basename "$redis_backup")" -C /data
    fi
    
    # Restore Weaviate data
    local weaviate_backup=$(find "$backup_dir" -name "weaviate_data_backup_*.tar.gz" -type f | sort -r | head -1)
    if [ -n "$weaviate_backup" ] && validate_backup "$weaviate_backup"; then
        log_info "Restoring Weaviate data..."
        docker volume rm memoria_weaviate_data 2>/dev/null || true
        docker volume create memoria_weaviate_data
        docker run --rm -v memoria_weaviate_data:/data -v "$backup_dir:/backup" alpine tar xzf "/backup/$(basename "$weaviate_backup")" -C /data
    fi
    
    log_success "Volumes restored successfully"
}

# Restore configuration
restore_configuration() {
    local backup_dir="$1"
    
    log_restore "Restoring configuration..."
    
    # Restore environment file
    local env_backup=$(find "$backup_dir" -name "env_backup_*" -type f | sort -r | head -1)
    if [ -n "$env_backup" ]; then
        log_info "Restoring environment configuration..."
        cp "$env_backup" .env
    fi
    
    # Restore Docker Compose
    local compose_backup=$(find "$backup_dir" -name "docker-compose_backup_*" -type f | sort -r | head -1)
    if [ -n "$compose_backup" ]; then
        log_info "Restoring Docker Compose configuration..."
        cp "$compose_backup" docker-compose.yml
    fi
    
    # Restore configuration files
    local config_backup=$(find "$backup_dir" -name "config_backup_*.tar.gz" -type f | sort -r | head -1)
    if [ -n "$config_backup" ] && validate_backup "$config_backup"; then
        log_info "Restoring configuration files..."
        tar xzf "$config_backup" -C .
    fi
    
    log_success "Configuration restored successfully"
}

# Full system restore
full_restore() {
    local backup_date="$1"
    
    log_restore "Starting full system restore..."
    
    # Find backup directory
    local backup_dir="$BACKUP_DIR"
    if [ -n "$backup_date" ]; then
        backup_dir="$BACKUP_DIR/$backup_date"
    fi
    
    if [ ! -d "$backup_dir" ]; then
        log_error "Backup directory not found: $backup_dir"
        return 1
    fi
    
    # Pre-restore checks
    pre_restore_checks
    
    # Stop services
    stop_services
    
    # Restore configuration
    restore_configuration "$backup_dir"
    
    # Restore volumes
    restore_volumes "$backup_dir"
    
    # Restore database
    local db_backup=$(find "$backup_dir" -name "database_backup_*.sql.gz" -type f | sort -r | head -1)
    if [ -n "$db_backup" ]; then
        restore_database "$db_backup"
    fi
    
    # Start services
    if ! start_services; then
        log_error "Failed to start services after restore"
        return 1
    fi
    
    # Post-restore checks
    if ! post_restore_checks; then
        log_error "Post-restore checks failed"
        return 1
    fi
    
    log_success "Full system restore completed"
}

# Start services
start_services() {
    log_restore "Starting services..."
    
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

# Post-restore checks
post_restore_checks() {
    log_restore "Running post-restore checks..."
    
    # Health check
    if ! ./scripts/health-check.sh --once; then
        log_error "Post-restore health check failed"
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
    
    log_success "Post-restore checks passed"
}

# Generate restore report
generate_restore_report() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local report_file="restore_report_$(date +%Y%m%d_%H%M%S).json"
    
    # Collect system information
    local disk_usage=$(df -h / | awk 'NR==2 {print $5}')
    local memory_usage=$(free -h | awk 'NR==2{printf "%s/%s", $3,$2}')
    local cpu_cores=$(nproc)
    local load_average=$(uptime | awk -F'load average:' '{print $2}')
    
    # Container information
    local total_containers=$(docker ps -q | wc -l)
    local running_containers=$(docker ps --format "{{.Names}}" | wc -l)
    
    # Database information
    local db_size=$(docker exec memoria-postgres-1 psql -U memoria -d memoria_db -t -c "SELECT pg_size_pretty(pg_database_size('memoria_db'));")
    
    # Generate report
    cat > "$report_file" << EOF
{
    "timestamp": "$timestamp",
    "restore_status": "success",
    "backup_date": "$BACKUP_DATE",
    "backup_type": "$BACKUP_TYPE",
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
    "database": {
        "size": "$db_size"
    },
    "backup_location": "$BACKUP_DIR"
}
EOF
    
    log_success "Restore report generated: $report_file"
}

# Interactive restore
interactive_restore() {
    log_restore "Starting interactive restore..."
    
    # List available backups
    list_backups
    
    # Prompt for backup selection
    echo -e "\n${CYAN}Enter backup date (YYYYMMDD) or leave empty for latest:${NC}"
    read -r backup_date
    
    # Prompt for confirmation
    if [ "$SKIP_CONFIRMATION" != "true" ]; then
        echo -e "\n${YELLOW}WARNING: This will overwrite all current data!${NC}"
        echo -e "${YELLOW}Are you sure you want to continue? (yes/no):${NC}"
        read -r confirmation
        
        if [ "$confirmation" != "yes" ]; then
            log_info "Restore cancelled by user")
            exit 0
        fi
    fi
    
    # Set backup date
    BACKUP_DATE="$backup_date"
    
    # Run full restore
    full_restore "$backup_date"
}

# Main function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Memoria AI Restore                        ║"
    echo "║              Complete System Restoration                     ║"
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
            echo "  --list             List available backups"
            echo "  --restore [DATE]   Restore from backup (interactive if no date)"
            echo "  --database FILE    Restore database from specific file"
            echo "  --volumes DIR      Restore volumes from specific directory"
            echo "  --config DIR       Restore configuration from specific directory"
            echo "  --full DATE        Full system restore from specific date"
            echo "  --validate FILE    Validate backup file"
            echo "  --report           Generate restore report"
            echo ""
            echo "Environment variables:"
            echo "  BACKUP_DIR         Backup directory (default: ./backups)"
            echo "  RESTORE_LOG        Restore log file (default: ./logs/restore.log)"
            echo "  RESTORE_TIMEOUT    Restore timeout (default: 3600)"
            echo "  FORCE_RESTORE      Force restore (default: false)"
            echo "  SKIP_CONFIRMATION  Skip confirmation prompts (default: false)"
            echo "  HEALTH_CHECK_TIMEOUT Health check timeout (default: 300)"
            echo "  BACKUP_DATE        Backup date (default: latest)"
            echo "  BACKUP_TYPE        Backup type (default: full)"
            exit 0
            ;;
        --list)
            list_backups
            ;;
        --restore)
            interactive_restore
            ;;
        --database)
            if [ -z "$2" ]; then
                log_error "Database backup file required"
                exit 1
            fi
            pre_restore_checks
            stop_services
            restore_database "$2"
            start_services
            post_restore_checks
            generate_restore_report
            ;;
        --volumes)
            if [ -z "$2" ]; then
                log_error "Backup directory required"
                exit 1
            fi
            pre_restore_checks
            stop_services
            restore_volumes "$2"
            start_services
            post_restore_checks
            generate_restore_report
            ;;
        --config)
            if [ -z "$2" ]; then
                log_error "Backup directory required"
                exit 1
            fi
            pre_restore_checks
            stop_services
            restore_configuration "$2"
            start_services
            post_restore_checks
            generate_restore_report
            ;;
        --full)
            if [ -z "$2" ]; then
                log_error "Backup date required"
                exit 1
            fi
            full_restore "$2"
            generate_restore_report
            ;;
        --validate)
            if [ -z "$2" ]; then
                log_error "Backup file required"
                exit 1
            fi
            validate_backup "$2"
            ;;
        --report)
            generate_restore_report
            ;;
        *)
            interactive_restore
            ;;
    esac
}

# Handle script arguments
main "$@"