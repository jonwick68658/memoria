#!/bin/bash
# Memoria AI Upgrade Rollback Script
# Safely rollback to previous version with comprehensive validation

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
BACKUP_DIR="${BACKUP_DIR:-./backups/pre-upgrade}"
ROLLBACK_LOG="${ROLLBACK_LOG:-./logs/rollback.log}"
REPORTS_DIR="${REPORTS_DIR:-./reports}"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
ROLLBACK_REPORT="${REPORTS_DIR}/rollback-report_${TIMESTAMP}.json"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$ROLLBACK_LOG"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$ROLLBACK_LOG"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$ROLLBACK_LOG"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$ROLLBACK_LOG"
}

# Create necessary directories
create_directories() {
    mkdir -p "$(dirname "$ROLLBACK_LOG")"
    mkdir -p "$REPORTS_DIR"
}

# Check if backup exists
check_backup_exists() {
    log_info "Checking for backup at: $BACKUP_DIR"
    
    if [ ! -d "$BACKUP_DIR" ]; then
        log_error "Backup directory not found: $BACKUP_DIR"
        log_error "Cannot proceed with rollback - no backup available"
        exit 1
    fi
    
    if [ ! -f "$BACKUP_DIR/docker-compose.yml" ]; then
        log_error "Backup appears incomplete - docker-compose.yml not found"
        exit 1
    fi
    
    log_success "Backup directory found and appears complete"
}

# Stop current services
stop_services() {
    log_info "Stopping current services..."
    
    if [ -f "docker-compose.yml" ]; then
        docker-compose down --remove-orphans 2>/dev/null || true
    fi
    
    # Remove containers and networks
    docker system prune -f 2>/dev/null || true
    
    log_success "Services stopped and cleaned up"
}

# Restore from backup
restore_backup() {
    log_info "Restoring from backup..."
    
    # Create backup of current state (in case we need to rollback the rollback)
    local current_backup="./backups/pre-rollback_${TIMESTAMP}"
    mkdir -p "$current_backup"
    
    if [ -f "docker-compose.yml" ]; then
        cp docker-compose.yml "$current_backup/"
    fi
    
    if [ -d "app" ]; then
        cp -r app "$current_backup/"
    fi
    
    if [ -f ".env" ]; then
        cp .env "$current_backup/"
    fi
    
    log_info "Current state backed up to: $current_backup"
    
    # Restore backup files
    log_info "Restoring backup files..."
    cp -r "$BACKUP_DIR"/* ./
    
    log_success "Backup restored successfully"
}

# Restore database
restore_database() {
    log_info "Restoring database from backup..."
    
    local db_backup="$BACKUP_DIR/database_backup.sql"
    
    if [ -f "$db_backup" ]; then
        # Start database container
        docker-compose up -d postgres
        
        # Wait for database to be ready
        log_info "Waiting for database to be ready..."
        local retries=30
        while [ $retries -gt 0 ]; do
            if docker-compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
                break
            fi
            sleep 2
            retries=$((retries - 1))
        done
        
        if [ $retries -eq 0 ]; then
            log_error "Database failed to start within timeout"
            exit 1
        fi
        
        # Restore database
        log_info "Restoring database..."
        docker-compose exec -T postgres psql -U postgres -d memoria < "$db_backup"
        
        log_success "Database restored successfully"
    else
        log_warning "No database backup found, skipping database restore"
    fi
}

# Restore Redis data
restore_redis() {
    log_info "Restoring Redis data..."
    
    local redis_backup="$BACKUP_DIR/redis_backup.rdb"
    
    if [ -f "$redis_backup" ]; then
        # Ensure Redis data directory exists
        mkdir -p redis-data
        
        # Copy Redis backup
        cp "$redis_backup" redis-data/dump.rdb
        
        log_success "Redis data restored successfully"
    else
        log_warning "No Redis backup found, skipping Redis restore"
    fi
}

# Restore Weaviate data
restore_weaviate() {
    log_info "Restoring Weaviate data..."
    
    local weaviate_backup="$BACKUP_DIR/weaviate_backup"
    
    if [ -d "$weaviate_backup" ]; then
        # Ensure Weaviate data directory exists
        mkdir -p weaviate-data
        
        # Copy Weaviate backup
        cp -r "$weaviate_backup"/* weaviate-data/
        
        log_success "Weaviate data restored successfully"
    else
        log_warning "No Weaviate backup found, skipping Weaviate restore"
    fi
}

# Start services
start_services() {
    log_info "Starting services..."
    
    # Pull images for the restored version
    docker-compose pull
    
    # Start services
    docker-compose up -d
    
    log_success "Services started"
}

# Validate rollback
validate_rollback() {
    log_info "Validating rollback..."
    
    local validation_failed=false
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # Check service health
    local services=("memoria-api-1" "memoria-postgres-1" "memoria-redis-1" "memoria-weaviate-1")
    
    for service in "${services[@]}"; do
        if docker inspect --format='{{.State.Status}}' "$service" 2>/dev/null | grep -q "running"; then
            log_success "$service is running"
        else
            log_error "$service is not running"
            validation_failed=true
        fi
    done
    
    # Test API connectivity
    log_info "Testing API connectivity..."
    local api_url="http://localhost:8000/health"
    local retries=10
    
    while [ $retries -gt 0 ]; do
        if curl -s "$api_url" >/dev/null 2>&1; then
            log_success "API is responding"
            break
        fi
        sleep 3
        retries=$((retries - 1))
    done
    
    if [ $retries -eq 0 ]; then
        log_error "API is not responding"
        validation_failed=true
    fi
    
    # Run basic tests
    log_info "Running basic validation tests..."
    if [ -f "scripts/health-check.sh" ]; then
        if ./scripts/health-check.sh --quick; then
            log_success "Health checks passed"
        else
            log_error "Health checks failed"
            validation_failed=true
        fi
    fi
    
    if [ "$validation_failed" = true ]; then
        log_error "Rollback validation failed"
        return 1
    else
        log_success "Rollback validation passed"
        return 0
    fi
}

# Generate rollback report
generate_rollback_report() {
    log_info "Generating rollback report..."
    
    cat > "$ROLLBACK_REPORT" << EOF
{
    "rollback": {
        "timestamp": "$(date -Iseconds)",
        "backup_source": "$BACKUP_DIR",
        "rollback_duration_seconds": $SECONDS,
        "validation_passed": true,
        "services": {
            "api": "$(docker inspect --format='{{.State.Status}}' memoria-api-1 2>/dev/null || echo 'not found')",
            "postgres": "$(docker inspect --format='{{.State.Status}}' memoria-postgres-1 2>/dev/null || echo 'not found')",
            "redis": "$(docker inspect --format='{{.State.Status}}' memoria-redis-1 2>/dev/null || echo 'not found')",
            "weaviate": "$(docker inspect --format='{{.State.Status}}' memoria-weaviate-1 2>/dev/null || echo 'not found')"
        },
        "files_restored": [
            "docker-compose.yml",
            "app/",
            ".env",
            "database_backup.sql",
            "redis_backup.rdb",
            "weaviate_backup/"
        ],
        "pre_rollback_backup": "./backups/pre-rollback_${TIMESTAMP}"
    }
}
EOF
    
    log_success "Rollback report generated: $ROLLBACK_REPORT"
}

# Cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups..."
    
    # Keep only last 5 pre-rollback backups
    find ./backups -name "pre-rollback_*" -type d | sort -r | tail -n +6 | xargs rm -rf 2>/dev/null || true
    
    log_success "Old backups cleaned up"
}

# Rollback main function
perform_rollback() {
    log_info "Starting rollback process..."
    
    local start_time=$SECONDS
    
    # Perform rollback steps
    check_backup_exists
    stop_services
    restore_backup
    restore_database
    restore_redis
    restore_weaviate
    start_services
    
    # Validate rollback
    if validate_rollback; then
        local duration=$((SECONDS - start_time))
        log_success "Rollback completed successfully in ${duration} seconds"
        
        # Generate report
        generate_rollback_report
        
        # Cleanup
        cleanup_old_backups
        
        return 0
    else
        log_error "Rollback failed validation"
        return 1
    fi
}

# Interactive rollback confirmation
confirm_rollback() {
    echo -e "${YELLOW}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    ROLLBACK CONFIRMATION                     ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo -e "${RED}WARNING: This will rollback to the previous version.${NC}"
    echo -e "${RED}All current data and configuration will be replaced.${NC}"
    echo ""
    
    if [ -d "$BACKUP_DIR" ]; then
        echo -e "${BLUE}Backup found:${NC} $BACKUP_DIR"
        echo -e "${BLUE}Backup created:${NC} $(ls -la "$BACKUP_DIR" | head -2 | tail -1 | awk '{print $6, $7, $8}')"
        echo ""
    fi
    
    read -p "Are you sure you want to proceed? [y/N]: " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        return 0
    else
        log_info "Rollback cancelled by user"
        return 1
    fi
}

# Main function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                 Memoria AI Rollback Tool                     ║"
    echo "║              Safe Upgrade Rollback System                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # Create directories
    create_directories
    
    # Initialize log
    echo "=== Rollback Process Started at $(date) ===" >> "$ROLLBACK_LOG"
    
    case "${1:-}" in
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --help, -h         Show this help message"
            echo "  --force            Skip confirmation prompt"
            echo "  --backup-dir DIR   Specify backup directory (default: ./backups/pre-upgrade)"
            echo ""
            echo "This script will rollback to the version backed up in the specified directory."
            echo "Make sure you have a valid backup before proceeding."
            ;;
        --force)
            log_info "Force mode enabled - skipping confirmation"
            perform_rollback
            ;;
        --backup-dir)
            if [ -n "$2" ]; then
                BACKUP_DIR="$2"
                shift 2
                if confirm_rollback; then
                    perform_rollback
                fi
            else
                log_error "Backup directory not specified"
                exit 1
            fi
            ;;
        *)
            if confirm_rollback; then
                perform_rollback
            fi
            ;;
    esac
    
    echo "=== Rollback Process Completed at $(date) ===" >> "$ROLLBACK_LOG"
}

# Handle script arguments
main "$@"