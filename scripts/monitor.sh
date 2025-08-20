#!/bin/bash
# Memoria AI Monitoring Script
# Real-time monitoring and alerting for system health

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
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"
ALERT_EMAIL="${ALERT_EMAIL:-}"
ALERT_THRESHOLD_CPU="${ALERT_THRESHOLD_CPU:-80}"
ALERT_THRESHOLD_MEMORY="${ALERT_THRESHOLD_MEMORY:-80}"
ALERT_THRESHOLD_DISK="${ALERT_THRESHOLD_DISK:-85}"
ALERT_THRESHOLD_RESPONSE_TIME="${ALERT_THRESHOLD_RESPONSE_TIME:-2.0}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"
LOG_FILE="${LOG_FILE:-./logs/monitoring.log}"
METRICS_FILE="${METRICS_FILE:-./logs/metrics.json}"

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

log_alert() {
    echo -e "${PURPLE}[ALERT]${NC} $1" | tee -a "$LOG_FILE"
}

# Create log directory
create_log_dir() {
    local log_dir=$(dirname "$LOG_FILE")
    if [ ! -d "$log_dir" ]; then
        mkdir -p "$log_dir"
    fi
}

# Send alert notification
send_alert() {
    local message=$1
    local severity=$2
    
    log_alert "[$severity] $message"
    
    # Send webhook notification
    if [ -n "$ALERT_WEBHOOK" ]; then
        curl -X POST "$ALERT_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"🚨 Memoria AI Alert: $message\",\"severity\":\"$severity\"}" \
            > /dev/null 2>&1 || true
    fi
    
    # Send email notification
    if [ -n "$ALERT_EMAIL" ] && command -v mail >/dev/null 2>&1; then
        echo "$message" | mail -s "Memoria AI Alert - $severity" "$ALERT_EMAIL"
    fi
}

# Check system metrics
check_system_metrics() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # CPU usage
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
    cpu_usage=${cpu_usage%.*}
    
    # Memory usage
    local memory_info=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    
    # Disk usage
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    # Log metrics
    echo "{\"timestamp\":\"$timestamp\",\"cpu\":$cpu_usage,\"memory\":$memory_info,\"disk\":$disk_usage}" >> "$METRICS_FILE"
    
    # Check thresholds
    if [ "$cpu_usage" -gt "$ALERT_THRESHOLD_CPU" ]; then
        send_alert "High CPU usage detected: ${cpu_usage}%" "WARNING"
    fi
    
    if [ "$memory_info" -gt "$ALERT_THRESHOLD_MEMORY" ]; then
        send_alert "High memory usage detected: ${memory_info}%" "WARNING"
    fi
    
    if [ "$disk_usage" -gt "$ALERT_THRESHOLD_DISK" ]; then
        send_alert "High disk usage detected: ${disk_usage}%" "CRITICAL"
    fi
}

# Check API health
check_api_health() {
    local response_time=$(curl -s -o /dev/null -w "%{time_total}" --max-time 10 "$API_BASE_URL/healthz")
    
    if [ $? -eq 0 ]; then
        if (( $(echo "$response_time > $ALERT_THRESHOLD_RESPONSE_TIME" | bc -l) )); then
            send_alert "API response time high: ${response_time}s" "WARNING"
        fi
    else
        send_alert "API health check failed" "CRITICAL"
    fi
}

# Check database connectivity
check_database() {
    if ! curl -s -f --max-time 10 "$API_BASE_URL/healthz/db" > /dev/null 2>&1; then
        send_alert "Database connectivity issue detected" "CRITICAL"
    fi
}

# Check Redis connectivity
check_redis() {
    if ! curl -s -f --max-time 10 "$API_BASE_URL/healthz/redis" > /dev/null 2>&1; then
        send_alert "Redis connectivity issue detected" "CRITICAL"
    fi
}

# Check Weaviate connectivity
check_weaviate() {
    if ! curl -s -f --max-time 10 "$API_BASE_URL/healthz/weaviate" > /dev/null 2>&1; then
        send_alert "Weaviate connectivity issue detected" "CRITICAL"
    fi
}

# Check Celery workers
check_celery() {
    if ! curl -s -f --max-time 10 "$API_BASE_URL/healthz/celery" > /dev/null 2>&1; then
        send_alert "Celery worker issue detected" "WARNING"
    fi
}

# Check Docker containers
check_containers() {
    local unhealthy=$(docker ps --format "{{.Names}}" | grep -v "Up" | wc -l)
    
    if [ "$unhealthy" -gt 0 ]; then
        local container_list=$(docker ps --format "{{.Names}}" | grep -v "Up")
        send_alert "Unhealthy containers detected: $container_list" "WARNING"
    fi
}

# Check log errors
check_log_errors() {
    local error_count=$(docker-compose logs --tail=100 | grep -i error | wc -l)
    
    if [ "$error_count" -gt 10 ]; then
        send_alert "High error rate in logs: $error_count errors" "WARNING"
    fi
}

# Check SSL certificate expiry
check_ssl_expiry() {
    local cert_file="/etc/ssl/certs/memoria.crt"
    
    if [ -f "$cert_file" ]; then
        local expiry=$(openssl x509 -enddate -noout -in "$cert_file" | cut -d= -f2)
        local expiry_epoch=$(date -d "$expiry" +%s)
        local current_epoch=$(date +%s)
        local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
        
        if [ "$days_until_expiry" -lt 7 ]; then
            send_alert "SSL certificate expires in $days_until_expiry days" "WARNING"
        fi
    fi
}

# Check backup status
check_backup_status() {
    local latest_backup=$(find backups/ -name "*.sql.gz" -type f -mtime -1 2>/dev/null | head -1)
    
    if [ -z "$latest_backup" ]; then
        send_alert "No recent backups found" "WARNING"
    fi
}

# Monitor services
monitor_services() {
    log_info "Starting service monitoring..."
    
    while true; do
        check_api_health
        check_database
        check_redis
        check_weaviate
        check_celery
        check_containers
        check_log_errors
        check_ssl_expiry
        check_backup_status
        
        sleep $CHECK_INTERVAL
    done
}

# Monitor system resources
monitor_system() {
    log_info "Starting system monitoring..."
    
    while true; do
        check_system_metrics
        sleep $CHECK_INTERVAL
    done
}

# Generate monitoring report
generate_report() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local report_file="monitoring_report_$(date +%Y%m%d_%H%M%S).json"
    
    # Collect metrics
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
    local memory_info=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    local api_response=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$API_BASE_URL/healthz")
    local response_time=$(curl -s -o /dev/null -w "%{time_total}" --max-time 10 "$API_BASE_URL/healthz")
    
    # Container status
    local total_containers=$(docker ps -q | wc -l)
    local healthy_containers=$(docker ps --format "{{.Status}}" | grep "Up" | wc -l)
    
    # Generate report
    cat > "$report_file" << EOF
{
    "timestamp": "$timestamp",
    "system": {
        "cpu_usage": "$cpu_usage%",
        "memory_usage": "$memory_info%",
        "disk_usage": "$disk_usage%"
    },
    "api": {
        "status_code": $api_response,
        "response_time": "${response_time}s"
    },
    "containers": {
        "total": $total_containers,
        "healthy": $healthy_containers
    },
    "services": {
        "database": $(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_BASE_URL/healthz/db"),
        "redis": $(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_BASE_URL/healthz/redis"),
        "weaviate": $(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_BASE_URL/healthz/weaviate"),
        "celery": $(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_BASE_URL/healthz/celery")
    }
}
EOF
    
    log_success "Monitoring report generated: $report_file"
}

# Dashboard mode
show_dashboard() {
    while true; do
        clear
        echo -e "${CYAN}"
        echo "╔══════════════════════════════════════════════════════════════╗"
        echo "║                    Memoria AI Monitoring                     ║"
        echo "║                    Real-time Dashboard                       ║"
        echo "╚══════════════════════════════════════════════════════════════╝"
        echo -e "${NC}"
        
        # System metrics
        echo -e "${GREEN}System Metrics:${NC}"
        echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')%"
        echo "Memory: $(free -h | awk 'NR==2{printf "%s/%s (%.0f%%)", $3,$2,$3*100/$2}')"
        echo "Disk: $(df -h / | awk 'NR==2{printf "%s/%s (%s)", $3,$2,$5}')"
        echo ""
        
        # Service status
        echo -e "${GREEN}Service Status:${NC}"
        echo "API: $(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_BASE_URL/healthz")"
        echo "Database: $(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_BASE_URL/healthz/db")"
        echo "Redis: $(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_BASE_URL/healthz/redis")"
        echo "Weaviate: $(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_BASE_URL/healthz/weaviate")"
        echo "Celery: $(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$API_BASE_URL/healthz/celery")"
        echo ""
        
        # Container status
        echo -e "${GREEN}Containers:${NC}"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        echo ""
        
        # Recent alerts
        echo -e "${GREEN}Recent Alerts:${NC}"
        tail -5 "$LOG_FILE" | grep "ALERT" || echo "No recent alerts"
        
        sleep $CHECK_INTERVAL
    done
}

# Main function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Memoria AI Monitoring                     ║"
    echo "║              Real-time Monitoring & Alerting                 ║"
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
            echo "  --services         Monitor services only"
            echo "  --system           Monitor system resources only"
            echo "  --dashboard        Show real-time dashboard"
            echo "  --report           Generate monitoring report"
            echo "  --once             Run checks once and exit"
            echo ""
            echo "Environment variables:"
            echo "  API_BASE_URL       API base URL (default: http://localhost:8000)"
            echo "  ALERT_WEBHOOK      Webhook URL for alerts"
            echo "  ALERT_EMAIL        Email address for alerts"
            echo "  CHECK_INTERVAL     Check interval in seconds (default: 30)"
            echo "  LOG_FILE           Log file path (default: ./logs/monitoring.log)"
            echo "  METRICS_FILE       Metrics file path (default: ./logs/metrics.json)"
            exit 0
            ;;
        --services)
            monitor_services
            ;;
        --system)
            monitor_system
            ;;
        --dashboard)
            show_dashboard
            ;;
        --report)
            generate_report
            ;;
        --once)
            check_system_metrics
            check_api_health
            check_database
            check_redis
            check_weaviate
            check_celery
            check_containers
            check_log_errors
            check_ssl_expiry
            check_backup_status
            ;;
        *)
            # Start both monitors in background
            monitor_system &
            monitor_services &
            wait
            ;;
    esac
}

# Handle script arguments
main "$@"