#!/bin/bash
# Memoria AI Upgrade Testing Script
# Comprehensive testing suite for post-upgrade validation

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
TEST_REPORT="${TEST_REPORT:-./reports/upgrade-test-report.json}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
TEST_TIMEOUT="${TEST_TIMEOUT:-30}"
MAX_RETRIES="${MAX_RETRIES:-5}"
REPORTS_DIR="${REPORTS_DIR:-./reports}"

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

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

# Test result tracking
test_result() {
    local test_name="$1"
    local status="$2"
    local message="$3"
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    case "$status" in
        PASS)
            PASSED_TESTS=$((PASSED_TESTS + 1))
            log_success "✓ $test_name: $message"
            ;;
        FAIL)
            FAILED_TESTS=$((FAILED_TESTS + 1))
            log_error "✗ $test_name: $message"
            ;;
        SKIP)
            SKIPPED_TESTS=$((SKIPPED_TESTS + 1))
            log_warning "- $test_name: $message"
            ;;
    esac
}

# Wait for services to be ready
wait_for_services() {
    log_info "Waiting for services to be ready..."
    
    local max_wait=60
    local elapsed=0
    
    while [ $elapsed -lt $max_wait ]; do
        if curl -s "$API_BASE_URL/health" >/dev/null 2>&1; then
            log_success "API is ready"
            return 0
        fi
        
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    log_error "Services failed to become ready within timeout"
    return 1
}

# Test API health endpoint
test_api_health() {
    local test_name="API Health Check"
    
    log_info "Testing API health endpoint..."
    
    local response=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/health" 2>/dev/null || echo -e "\n000")
    local body=$(echo "$response" | head -n -1)
    local status=$(echo "$response" | tail -n 1)
    
    if [ "$status" = "200" ]; then
        local status_value=$(echo "$body" | jq -r '.status' 2>/dev/null || echo "")
        if [ "$status_value" = "healthy" ]; then
            test_result "$test_name" "PASS" "API is healthy"
            return 0
        else
            test_result "$test_name" "FAIL" "API returned unhealthy status: $status_value"
            return 1
        fi
    else
        test_result "$test_name" "FAIL" "API returned status $status"
        return 1
    fi
}

# Test database connectivity
test_database_connectivity() {
    local test_name="Database Connectivity"
    
    log_info "Testing database connectivity..."
    
    local response=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/health/db" 2>/dev/null || echo -e "\n000")
    local body=$(echo "$response" | head -n -1)
    local status=$(echo "$response" | tail -n 1)
    
    if [ "$status" = "200" ]; then
        local db_status=$(echo "$body" | jq -r '.database' 2>/dev/null || echo "")
        if [ "$db_status" = "connected" ]; then
            test_result "$test_name" "PASS" "Database is connected"
            return 0
        else
            test_result "$test_name" "FAIL" "Database connection failed: $db_status"
            return 1
        fi
    else
        test_result "$test_name" "FAIL" "Database health check returned status $status"
        return 1
    fi
}

# Test Redis connectivity
test_redis_connectivity() {
    local test_name="Redis Connectivity"
    
    log_info "Testing Redis connectivity..."
    
    local response=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/health/redis" 2>/dev/null || echo -e "\n000")
    local body=$(echo "$response" | head -n -1)
    local status=$(echo "$response" | tail -n 1)
    
    if [ "$status" = "200" ]; then
        local redis_status=$(echo "$body" | jq -r '.redis' 2>/dev/null || echo "")
        if [ "$redis_status" = "connected" ]; then
            test_result "$test_name" "PASS" "Redis is connected"
            return 0
        else
            test_result "$test_name" "FAIL" "Redis connection failed: $redis_status"
            return 1
        fi
    else
        test_result "$test_name" "FAIL" "Redis health check returned status $status"
        return 1
    fi
}

# Test Weaviate connectivity
test_weaviate_connectivity() {
    local test_name="Weaviate Connectivity"
    
    log_info "Testing Weaviate connectivity..."
    
    local response=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/health/weaviate" 2>/dev/null || echo -e "\n000")
    local body=$(echo "$response" | head -n -1)
    local status=$(echo "$response" | tail -n 1)
    
    if [ "$status" = "200" ]; then
        local weaviate_status=$(echo "$body" | jq -r '.weaviate' 2>/dev/null || echo "")
        if [ "$weaviate_status" = "connected" ]; then
            test_result "$test_name" "PASS" "Weaviate is connected"
            return 0
        else
            test_result "$test_name" "FAIL" "Weaviate connection failed: $weaviate_status"
            return 1
        fi
    else
        test_result "$test_name" "FAIL" "Weaviate health check returned status $status"
        return 1
    fi
}

# Test memory creation
test_memory_creation() {
    local test_name="Memory Creation"
    
    log_info "Testing memory creation..."
    
    local test_data='{
        "content": "Test memory for upgrade validation",
        "metadata": {
            "source": "upgrade-test",
            "tags": ["test", "upgrade", "validation"]
        }
    }'
    
    local response=$(curl -s -w "\n%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -d "$test_data" \
        "$API_BASE_URL/memories" 2>/dev/null || echo -e "\n000")
    
    local body=$(echo "$response" | head -n -1)
    local status=$(echo "$response" | tail -n 1)
    
    if [ "$status" = "201" ]; then
        local memory_id=$(echo "$body" | jq -r '.id' 2>/dev/null || echo "")
        if [ -n "$memory_id" ]; then
            test_result "$test_name" "PASS" "Memory created with ID: $memory_id"
            # Store for cleanup
            echo "$memory_id" >> /tmp/test_memory_ids
            return 0
        else
            test_result "$test_name" "FAIL" "Memory created but no ID returned"
            return 1
        fi
    else
        test_result "$test_name" "FAIL" "Memory creation failed with status $status"
        return 1
    fi
}

# Test memory retrieval
test_memory_retrieval() {
    local test_name="Memory Retrieval"
    
    log_info "Testing memory retrieval..."
    
    # Get a memory ID from the list
    local memory_id=$(tail -n 1 /tmp/test_memory_ids 2>/dev/null || echo "")
    
    if [ -z "$memory_id" ]; then
        test_result "$test_name" "SKIP" "No test memory available"
        return 0
    fi
    
    local response=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/memories/$memory_id" 2>/dev/null || echo -e "\n000