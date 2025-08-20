#!/bin/bash
# Memoria AI Health Check Script
# Comprehensive health monitoring for all services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
TIMEOUT=10
MAX_RETRIES=3
RETRY_DELAY=5

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check HTTP endpoint
check_http() {
    local url=$1
    local name=$2
    
    log_info "Checking $name at $url..."
    
    for i in $(seq 1 $MAX_RETRIES); do
        if curl -s -f --max-time $TIMEOUT "$url" > /dev/null 2>&1; then
            log_success "$name is healthy"
            return 0
        fi
        
        if [ $i -lt $MAX_RETRIES ]; then
            log_warning "$name check failed, retrying in ${RETRY_DELAY}s..."
            sleep $RETRY_DELAY
        fi
    done
    
    log_error "$name is unhealthy"
    return 1
}

# Check database connectivity
check_database() {
    log_info "Checking database connectivity..."
    
    if curl -s -f --max-time $TIMEOUT "$API_BASE_URL/healthz/db" > /dev/null 2>&1; then
        log_success "Database is healthy"
        return 0
    else
        log_error "Database is unhealthy"
        return 1
    fi
}

# Check Redis connectivity
check_redis() {
    log_info "Checking Redis connectivity..."
    
    if curl -s -f --max-time $TIMEOUT "$API_BASE_URL/healthz/redis" > /dev/null 2>&1; then
        log_success "Redis is healthy"
        return 0
    else
        log_error "Redis is unhealthy"
        return 1
    fi
}

# Check Weaviate connectivity
check_weaviate() {
    log_info "Checking Weaviate connectivity..."
    
    if curl -s -f --max-time $TIMEOUT "$API_BASE_URL/healthz/weaviate" > /dev/null 2>&1; then
        log_success "Weaviate is healthy"
        return 0
    else
        log_error "Weaviate is unhealthy"
        return 1
    fi
}

# Check Celery workers
check_celery() {
    log_info "Checking Celery workers..."
    
    if curl -s -f --max-time $TIMEOUT "$API_BASE_URL/healthz/celery" > /dev/null 2>&1; then
        log_success "Celery workers are healthy"
        return 0
    else
        log_error "Celery workers are unhealthy"
        return 1
    fi
}

# Check disk space
check_disk_space() {
    log_info "Checking disk space..."
    
    local usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [ "$usage" -lt 80 ]; then
        log_success "Disk space OK (${usage}% used)"
        return 0
    elif [ "$usage" -lt 90 ]; then
        log_warning "Disk space warning (${usage}% used)"
        return 0
    else
        log_error "Disk space critical (${usage}% used)"
        return 1
    fi
}

# Check memory usage
check_memory() {
    log_info "Checking memory usage..."
    
    local usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    
    if [ "$usage" -lt 80 ]; then
        log_success "Memory usage OK (${usage}% used)"
        return 0
    elif [ "$usage" -lt 90 ]; then
        log_warning "Memory usage warning (${usage}% used)"
        return 0
    else
        log_error "Memory usage critical (${usage}% used)"
        return 1
    fi
}

# Check Docker containers
check_docker_containers() {
    log_info "Checking Docker containers..."
    
    local unhealthy=$(docker ps --format "table {{.Names}}\t{{.Status}}" | grep -v "Up" | wc -l)
    
    if [ "$unhealthy" -eq 0 ]; then
        log_success "All Docker containers are healthy"
        return 0
    else
        log_error "$unhealthy Docker containers are unhealthy"
        docker ps --format "table {{.Names}}\t{{.Status}}" | grep -v "Up"
        return 1
    fi
}

# Check SSL certificates
check_ssl() {
    log_info "Checking SSL certificates..."
    
    local cert_file="/etc/ssl/certs/memoria.crt"
    
    if [ -f "$cert_file" ]; then
        local expiry=$(openssl x509 -enddate -noout -in "$cert_file" | cut -d= -f2)
        local expiry_epoch=$(date -d "$expiry" +%s)
        local current_epoch=$(date +%s)
        local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
        
        if [ "$days_until_expiry" -gt 30 ]; then
            log_success "SSL certificate valid for $days_until_expiry days"
            return 0
        elif [ "$days_until_expiry" -gt 7 ]; then
            log_warning "SSL certificate expires in $days_until_expiry days"
            return 0
        else
            log_error "SSL certificate expires in $days_until_expiry days"
            return 1
        fi
    else
        log_warning "SSL certificate file not found"
        return 0
    fi
}

# Check API response time
check_response_time() {
    log_info "Checking API response time..."
    
    local response_time=$(curl -s -o /dev/null -w "%{time_total}" --max-time $TIMEOUT "$API_BASE_URL/healthz")
    
    if (( $(echo "$response_time < 1.0" | bc -l) )); then
        log_success "API response time OK (${response_time}s)"
        return 0
    elif (( $(echo "$response_time < 5.0" | bc -l) )); then
        log_warning "API response time warning (${response_time}s)"
        return 0
    else
        log_error "API response time critical (${response_time}s)"
        return 1
    fi
}

# Check log files for errors
check_logs() {
    log_info "Checking recent logs for errors..."
    
    local error_count=$(docker-compose logs --tail=100 | grep -i error | wc -l)
    
    if [ "$error_count" -eq 0 ]; then
        log_success "No recent errors in logs"
        return 0
    elif [ "$error_count" -lt 10 ]; then
        log_warning "$error_count errors found in recent logs"
        return 0
    else
        log_error "$error_count errors found in recent logs"
        return 1
    fi
}

# Check backup status
check_backups() {
    log_info "Checking backup status..."
    
    local latest_backup=$(find backups/ -name "*.sql" -type f -mtime -1 | head -1)
    
    if [ -n "$latest_backup" ]; then
        log_success "Recent backup found: $(basename $latest_backup)"
        return 0
    else
        log_warning "No recent backups found"
        return 0
    fi
}

# Check monitoring services
check_monitoring() {
    log_info "Checking monitoring services..."
    
    local services=(
        "http://localhost:3000:Grafana"
        "http://localhost:9090:Prometheus"
        "http://localhost:5555:Flower"
    )
    
    for service in "${services[@]}"; do
        IFS=':' read -r url name <<< "$service"
        check_http "$url" "$name"
    done
}

# Generate health report
generate_report() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local report_file="health_report_$(date +%Y%m%d_%H%M%S).json"
    
    cat > "$report_file" << EOF
{
    "timestamp": "$timestamp",
    "api_base_url": "$API_BASE_URL",
    "checks": {
        "api": $(check_http "$API_BASE_URL/healthz" "API" && echo "true" || echo "false"),
        "database": $(check_database && echo "true" || echo "false"),
        "redis": $(check_redis && echo "true" || echo "false"),
        "weaviate": $(check_weaviate && echo "true" || echo "false"),
        "celery": $(check_celery && echo "true" || echo "false"),
        "disk_space": $(check_disk_space && echo "true" || echo "false"),
        "memory": $(check_memory && echo "true" || echo "false"),
        "docker_containers": $(check_docker_containers && echo "true" || echo "false"),
        "ssl": $(check_ssl && echo "true" || echo "false"),
        "response_time": $(check_response_time && echo "true" || echo "false"),
        "logs": $(check_logs && echo "true" || echo "false"),
        "backups": $(check_backups && echo "true" || echo "false")
    }
}
EOF
    
    log_success "Health report generated: $report_file"
}

# Run all health checks
run_all_checks() {
    log_info "Running comprehensive health checks..."
    
    local failed_checks=0
    
    # Core services
    check_http "$API_BASE_URL/healthz" "API" || ((failed_checks++))
    check_database || ((failed_checks++))
    check_redis || ((failed_checks++))
    check_weaviate || ((failed_checks++))
    check_celery || ((failed_checks++))
    
    # System resources
    check_disk_space || ((failed_checks++))
    check_memory || ((failed_checks++))
    check_docker_containers || ((failed_checks++))
    
    # Performance and monitoring
    check_response_time || ((failed_checks++))
    check_logs || ((failed_checks++))
    check_backups || ((failed_checks++))
    
    # SSL and certificates
    check_ssl || ((failed_checks++))
    
    # Generate report
    generate_report
    
    if [ $failed_checks -eq 0 ]; then
        log_success "All health checks passed! 🎉"
        return 0
    else
        log_error "$failed_checks health checks failed"
        return 1
    fi
}

# Watch mode
watch_mode() {
    local interval=${1:-60}
    
    log_info "Starting watch mode (interval: ${interval}s)..."
    
    while true; do
        clear
        echo -e "${GREEN}"
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║                    Memoria AI Health Monitor                 ║"
        echo "║                    Watching every ${interval}s...              ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        echo -e "${NC}"
        
        run_all_checks
        
        echo ""
        log_info "Next check in ${interval}s... (Press Ctrl+C to stop)"
        sleep $interval
    done
}

# Main function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Memoria AI Health Check                   ║"
    echo "║              Comprehensive System Monitoring                 ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    case "${1:-}" in
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --help, -h         Show this help message"
            echo "  --watch, -w [SEC]  Run in watch mode (default: 60s)"
            echo "  --report           Generate JSON health report"
            echo "  --monitoring       Check monitoring services"
            echo "  --quick            Run only core checks"
            echo ""
            echo "Environment variables:"
            echo "  API_BASE_URL       API base URL (default: http://localhost:8000)"
            echo "  TIMEOUT            Request timeout in seconds (default: 10)"
            echo "  MAX_RETRIES        Maximum retry attempts (default: 3)"
            exit 0
            ;;
        --watch|-w)
            watch_mode "${2:-60}"
            ;;
        --report)
            generate_report
            ;;
        --monitoring)
            check_monitoring
            ;;
        --quick)
            check_http "$API_BASE_URL/healthz" "API"
            check_database
            check_redis
            check_celery
            ;;
        *)
            run_all_checks
            ;;
    esac
}

# Handle script arguments
main "$@"