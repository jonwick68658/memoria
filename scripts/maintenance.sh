#!/bin/bash
# Memoria AI Maintenance Script
# Comprehensive maintenance tasks for system optimization

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
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-30}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-90}"
TEMP_RETENTION_DAYS="${TEMP_RETENTION_DAYS:-7}"
DOCKER_PRUNE="${DOCKER_PRUNE:-true}"
DATABASE_VACUUM="${DATABASE_VACUUM:-true}"
INDEX_OPTIMIZATION="${INDEX_OPTIMIZATION:-true}"
CACHE_CLEAR="${CACHE_CLEAR:-true}"
LOG_FILE="${LOG_FILE:-./logs/maintenance.log}"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

log_maintenance() {
    echo -e "${PURPLE}[MAINTENANCE]${NC} $1" | tee -a "$LOG_FILE"
}

# Create log directory
create_log_dir() {
    local log_dir=$(dirname "$LOG_FILE")
    if [ ! -d "$log_dir" ]; then
        mkdir -p "$log_dir"
    fi
}

# Clean old log files
clean_logs() {
    log_maintenance "Cleaning old log files..."
    
    # Application logs
    find ./logs -name "*.log" -type f -mtime +$LOG_RETENTION_DAYS -delete 2>/dev/null || true
    
    # Docker logs
    docker system prune -f --volumes > /dev/null 2>&1 || true
    
    # System logs
    find /var/log -name "*.log.*" -type f -mtime +$LOG_RETENTION_DAYS -delete 2>/dev/null || true
    
    log_success "Log files cleaned"
}

# Clean temporary files
clean_temp_files() {
    log_maintenance "Cleaning temporary files..."
    
    # Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type f -name "*.pyo" -delete 2>/dev/null || true
    
    # Temporary files
    find /tmp -name "memoria-*" -type f -mtime +$TEMP_RETENTION_DAYS -delete 2>/dev/null || true
    find /tmp -name "celery-*" -type f -mtime +$TEMP_RETENTION_DAYS -delete 2>/dev/null || true
    
    # Upload temp files
    find ./uploads/temp -type f -mtime +$TEMP_RETENTION_DAYS -delete 2>/dev/null || true
    
    log_success "Temporary files cleaned"
}

# Clean old backups
clean_backups() {
    log_maintenance "Cleaning old backups..."
    
    # Local backups
    find ./backups -name "*.sql.gz" -type f -mtime +$BACKUP_RETENTION_DAYS -delete 2>/dev/null || true
    find ./backups -name "*.tar.gz" -type f -mtime +$BACKUP_RETENTION_DAYS -delete 2>/dev/null || true
    find ./backups -name "*.enc" -type f -mtime +$BACKUP_RETENTION_DAYS -delete 2>/dev/null || true
    
    # S3 backups (if configured)
    if [ -n "$S3_BUCKET" ] && command -v aws >/dev/null 2>&1; then
        aws s3 ls "s3://${S3_BUCKET}/backups/" | \
            awk '{print $4}' | \
            while read -r file; do
                local file_date=$(echo "$file" | grep -o '[0-9]\{8\}' | head -1)
                local file_age=$(( ($(date +%s) - $(date -d "$file_date" +%s)) / 86400 ))
                
                if [ "$file_age" -gt "$BACKUP_RETENTION_DAYS" ]; then
                    aws s3 rm "s3://${S3_BUCKET}/backups/$file"
                    log_info "Deleted old S3 backup: $file"
                fi
            done
    fi
    
    log_success "Old backups cleaned"
}

# Docker maintenance
docker_maintenance() {
    log_maintenance "Performing Docker maintenance..."
    
    if [ "$DOCKER_PRUNE" = "true" ]; then
        # Clean unused containers
        docker container prune -f
        
        # Clean unused images
        docker image prune -f
        
        # Clean unused networks
        docker network prune -f
        
        # Clean unused volumes
        docker volume prune -f
        
        # Clean build cache
        docker builder prune -f
        
        log_success "Docker maintenance completed"
    else
        log_info "Docker maintenance skipped (DOCKER_PRUNE=false)"
    fi
}

# Database maintenance
database_maintenance() {
    log_maintenance "Performing database maintenance..."
    
    if [ "$DATABASE_VACUUM" = "true" ]; then
        # Stop application services
        docker-compose stop memoria-api
        
        # Vacuum database
        docker exec memoria-postgres-1 psql -U memoria -d memoria_db -c "VACUUM ANALYZE;"
        
        # Reindex database
        docker exec memoria-postgres-1 psql -U memoria -d memoria_db -c "REINDEX DATABASE memoria_db;"
        
        # Update statistics
        docker exec memoria-postgres-1 psql -U memoria -d memoria_db -c "ANALYZE;"
        
        # Start application services
        docker-compose start memoria-api
        
        log_success "Database maintenance completed"
    else
        log_info "Database maintenance skipped (DATABASE_VACUUM=false)"
    fi
}

# Index optimization
optimize_indexes() {
    log_maintenance "Optimizing indexes..."
    
    if [ "$INDEX_OPTIMIZATION" = "true" ]; then
        # Weaviate index optimization
        curl -X POST "$API_BASE_URL/admin/optimize-indexes" \
            -H "Content-Type: application/json" \
            -d '{"force": true}' || true
        
        # PostgreSQL index optimization
        docker exec memoria-postgres-1 psql -U memoria -d memoria_db -c "
            SELECT schemaname, tablename, attname, n_distinct, correlation 
            FROM pg_stats 
            WHERE schemaname NOT IN ('information_schema', 'pg_catalog')
            ORDER BY n_distinct DESC;
        "
        
        log_success "Index optimization completed"
    else
        log_info "Index optimization skipped (INDEX_OPTIMIZATION=false)"
    fi
}

# Cache maintenance
cache_maintenance() {
    log_maintenance "Performing cache maintenance..."
    
    if [ "$CACHE_CLEAR" = "true" ]; then
        # Clear Redis cache
        docker exec memoria-redis-1 redis-cli FLUSHALL
        
        # Clear application cache
        curl -X POST "$API_BASE_URL/admin/clear-cache" \
            -H "Content-Type: application/json" \
            -d '{"force": true}' || true
        
        log_success "Cache maintenance completed"
    else
        log_info "Cache maintenance skipped (CACHE_CLEAR=false)"
    fi
}

# Security updates
security_updates() {
    log_maintenance "Checking for security updates..."
    
    # Update system packages
    apt-get update > /dev/null 2>&1 || true
    
    # Check for security updates
    local security_updates=$(apt-get -s upgrade | grep -i security | wc -l)
    
    if [ "$security_updates" -gt 0 ]; then
        log_warning "$security_updates security updates available"
        
        # Create security report
        apt-get -s upgrade | grep -i security > security_updates_$(date +%Y%m%d).txt
        log_info "Security updates saved to security_updates_$(date +%Y%m%d).txt"
    else
        log_success "No security updates available"
    fi
    
    # Update Python packages
    pip list --outdated --format=json > python_updates.json || true
    
    log_success "Security update check completed"
}

# Performance optimization
performance_optimization() {
    log_maintenance "Performing performance optimization..."
    
    # Optimize Docker containers
    docker system prune -f
    
    # Optimize database queries
    docker exec memoria-postgres-1 psql -U memoria -d memoria_db -c "
        SELECT query, calls, total_time, mean_time 
        FROM pg_stat_statements 
        ORDER BY total_time DESC 
        LIMIT 10;
    " > slow_queries_$(date +%Y%m%d).txt
    
    # Optimize Celery workers
    docker exec memoria-celery-1 celery -A app.tasks inspect active > celery_status.txt
    
    log_success "Performance optimization completed"
}

# Health check
health_check() {
    log_maintenance "Performing health check..."
    
    # Run health check script
    ./scripts/health-check.sh --once
    
    # Check disk space
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 90 ]; then
        log_error "Critical disk space: ${disk_usage}%"
        send_alert "Critical disk space: ${disk_usage}%" "CRITICAL"
    fi
    
    # Check memory usage
    local memory_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    if [ "$memory_usage" -gt 95 ]; then
        log_error "Critical memory usage: ${memory_usage}%"
        send_alert "Critical memory usage: ${memory_usage}%" "CRITICAL"
    fi
    
    log_success "Health check completed"
}

# Generate maintenance report
generate_report() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local report_file="maintenance_report_$(date +%Y%m%d_%H%M%S).json"
    
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
    "maintenance_tasks": {
        "logs_cleaned": true,
        "temp_files_cleaned": true,
        "backups_cleaned": true,
        "docker_maintenance": $DOCKER_PRUNE,
        "database_maintenance": $DATABASE_VACUUM,
        "index_optimization": $INDEX_OPTIMIZATION,
        "cache_maintenance": $CACHE_CLEAR
    }
}
EOF
    
    log_success "Maintenance report generated: $report_file"
}

# Schedule maintenance
schedule_maintenance() {
    log_maintenance "Scheduling maintenance tasks..."
    
    # Create cron job for daily maintenance
    cat > /etc/cron.d/memoria-maintenance << EOF
# Memoria AI Daily Maintenance
0 2 * * * root cd /workspaces/memoria && ./scripts/maintenance.sh --daily >> /var/log/memoria-maintenance.log 2>&1
0 6 * * 0 root cd /workspaces/memoria && ./scripts/maintenance.sh --weekly >> /var/log/memoria-maintenance.log 2>&1
0 1 * * 1 root cd /workspaces/memoria && ./scripts/backup.sh --backup >> /var/log/memoria-backup.log 2>&1
EOF
    
    log_success "Maintenance scheduled"
}

# Run daily maintenance
run_daily_maintenance() {
    log_maintenance "Running daily maintenance..."
    
    clean_logs
    clean_temp_files
    clean_backups
    cache_maintenance
    health_check
    
    log_success "Daily maintenance completed"
}

# Run weekly maintenance
run_weekly_maintenance() {
    log_maintenance "Running weekly maintenance..."
    
    run_daily_maintenance
    docker_maintenance
    database_maintenance
    optimize_indexes
    performance_optimization
    security_updates
    
    log_success "Weekly maintenance completed"
}

# Main function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Memoria AI Maintenance                    ║"
    echo "║              Comprehensive System Maintenance                ║"
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
            echo "  --daily            Run daily maintenance"
            echo "  --weekly           Run weekly maintenance"
            echo "  --logs             Clean log files only"
            echo "  --temp             Clean temporary files only"
            echo "  --backups          Clean old backups only"
            echo "  --docker           Docker maintenance only"
            echo "  --database         Database maintenance only"
            echo "  --cache            Cache maintenance only"
            echo "  --security         Security updates only"
            echo "  --performance      Performance optimization only"
            echo "  --health           Health check only"
            echo "  --report           Generate maintenance report"
            echo "  --schedule         Schedule maintenance tasks"
            echo "  --all              Run all maintenance tasks"
            echo ""
            echo "Environment variables:"
            echo "  LOG_RETENTION_DAYS  Days to keep logs (default: 30)"
            echo "  BACKUP_RETENTION_DAYS Days to keep backups (default: 90)"
            echo "  TEMP_RETENTION_DAYS Days to keep temp files (default: 7)"
            echo "  DOCKER_PRUNE       Enable Docker pruning (default: true)"
            echo "  DATABASE_VACUUM    Enable database vacuum (default: true)"
            echo "  INDEX_OPTIMIZATION Enable index optimization (default: true)"
            echo "  CACHE_CLEAR        Enable cache clearing (default: true)"
            exit 0
            ;;
        --daily)
            run_daily_maintenance
            ;;
        --weekly)
            run_weekly_maintenance
            ;;
        --logs)
            clean_logs
            ;;
        --temp)
            clean_temp_files
            ;;
        --backups)
            clean_backups
            ;;
        --docker)
            docker_maintenance
            ;;
        --database)
            database_maintenance
            ;;
        --cache)
            cache_maintenance
            ;;
        --security)
            security_updates
            ;;
        --performance)
            performance_optimization
            ;;
        --health)
            health_check
            ;;
        --report)
            generate_report
            ;;
        --schedule)
            schedule_maintenance
            ;;
        --all)
            run_weekly_maintenance
            ;;
        *)
            run_daily_maintenance
            ;;
    esac
}

# Handle script arguments
main "$@"