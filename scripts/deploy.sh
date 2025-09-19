#!/bin/bash
# Memoria AI Deployment Script
# Supports deployment to staging and production environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Configuration
PROJECT_NAME="memoria"
STAGING_HOST="${STAGING_HOST:-staging.memoria.ai}"
PRODUCTION_HOST="${PRODUCTION_HOST:-memoria.ai}"
DEPLOY_USER="${DEPLOY_USER:-deploy}"
BACKUP_RETENTION_DAYS=30

# Check if required environment variables are set
check_env_vars() {
    local env=$1
    
    case $env in
        staging)
            required_vars=("STAGING_HOST" "STAGING_USER" "STAGING_KEY")
            ;;
        production)
            required_vars=("PRODUCTION_HOST" "PRODUCTION_USER" "PRODUCTION_KEY")
            ;;
        *)
            log_error "Invalid environment: $env"
            exit 1
            ;;
    esac
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "Environment variable $var is required for $env deployment"
            exit 1
        fi
    done
}

# Build application
build_app() {
    log_info "Building application..."
    
    # Clean previous builds
    make clean
    
    # Run tests
    make ci-test
    
    # Run security checks
    make ci-security
    
    # Build Docker image
    docker build -t ${PROJECT_NAME}:latest .
    docker tag ${PROJECT_NAME}:latest ${PROJECT_NAME}:$(git rev-parse --short HEAD)
    
    log_success "Application built successfully"
}

# Backup database
backup_database() {
    local env=$1
    local host=$2
    local user=$3
    
    log_info "Creating database backup..."
    
    local backup_file="backup_${env}_$(date +%Y%m%d_%H%M%S).sql"
    
    ssh -i ${DEPLOY_KEY} ${user}@${host} \
        "docker exec ${PROJECT_NAME}-postgres-1 pg_dump -U memoria memoria_db" > ${backup_file}
    
    # Upload backup to S3 or other storage
    if [ -n "$BACKUP_S3_BUCKET" ]; then
        aws s3 cp ${backup_file} s3://${BACKUP_S3_BUCKET}/backups/
        log_success "Backup uploaded to S3: ${backup_file}"
    fi
    
    # Clean old backups locally
    find . -name "backup_${env}_*.sql" -mtime +${BACKUP_RETENTION_DAYS} -delete
    
    log_success "Database backup created: ${backup_file}"
}

# Deploy to environment
deploy_to_env() {
    local env=$1
    local host=$2
    local user=$3
    
    log_info "Deploying to $env environment..."
    
    # Create deployment directory
    ssh -i ${DEPLOY_KEY} ${user}@${host} "mkdir -p /opt/${PROJECT_NAME}"
    
    # Copy deployment files
    scp -i ${DEPLOY_KEY} docker-compose.yml ${user}@${host}:/opt/${PROJECT_NAME}/
    scp -i ${DEPLOY_KEY} .env.${env} ${user}@${host}:/opt/${PROJECT_NAME}/.env
    scp -i ${DEPLOY_KEY} -r scripts/ ${user}@${host}:/opt/${PROJECT_NAME}/
    
    # Copy SSL certificates if they exist
    if [ -d "ssl" ]; then
        scp -i ${DEPLOY_KEY} -r ssl/ ${user}@${host}:/opt/${PROJECT_NAME}/
    fi
    
    # Deploy application
    ssh -i ${DEPLOY_KEY} ${user}@${host} << 'ENDSSH'
        cd /opt/${PROJECT_NAME}
        
        # Pull latest images
        docker-compose pull
        
        # Stop existing services
        docker-compose down
        
        # Start services
        docker-compose up -d
        
        # Wait for services to be healthy
        sleep 30
        
        # Run health checks
        curl -f http://localhost:8000/healthz || exit 1
        
        # Run database migrations
        docker-compose exec memoria-api alembic upgrade head
        
        # Clean up old images
        docker image prune -f
ENDSSH
    
    log_success "Deployed to $env successfully"
}

# Health check after deployment
health_check() {
    local env=$1
    local host=$2
    
    log_info "Running health checks..."
    
    # Wait for deployment to be ready
    sleep 60
    
    # Check API health
    if curl -f https://${host}/healthz > /dev/null 2>&1; then
        log_success "API health check passed"
    else
        log_error "API health check failed"
        exit 1
    fi
    
    # Check database connectivity
    if curl -f https://${host}/healthz/db > /dev/null 2>&1; then
        log_success "Database health check passed"
    else
        log_error "Database health check failed"
        exit 1
    fi
    
    log_success "All health checks passed"
}

# Rollback deployment
rollback() {
    local env=$1
    local host=$2
    local user=$3
    
    log_warning "Rolling back deployment..."
    
    ssh -i ${DEPLOY_KEY} ${user}@${host} << 'ENDSSH'
        cd /opt/${PROJECT_NAME}
        
        # Stop current services
        docker-compose down
        
        # Restore previous version
        docker tag ${PROJECT_NAME}:previous ${PROJECT_NAME}:latest
        
        # Start services with previous version
        docker-compose up -d
        
        # Wait for services to be ready
        sleep 30
        
        # Run health checks
        curl -f http://localhost:8000/healthz || exit 1
ENDSSH
    
    log_success "Rollback completed"
}

# Deploy to staging
deploy_staging() {
    log_info "Starting staging deployment..."
    
    check_env_vars "staging"
    
    build_app
    
    backup_database "staging" "${STAGING_HOST}" "${STAGING_USER}"
    
    deploy_to_env "staging" "${STAGING_HOST}" "${STAGING_USER}"
    
    health_check "staging" "${STAGING_HOST}"
    
    log_success "Staging deployment completed"
}

# Deploy to production
deploy_production() {
    log_info "Starting production deployment..."
    
    check_env_vars "production"
    
    # Confirm production deployment
    read -p "Are you sure you want to deploy to production? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "Production deployment cancelled"
        exit 0
    fi
    
    build_app
    
    backup_database "production" "${PRODUCTION_HOST}" "${PRODUCTION_USER}"
    
    deploy_to_env "production" "${PRODUCTION_HOST}" "${PRODUCTION_USER}"
    
    health_check "production" "${PRODUCTION_HOST}"
    
    log_success "Production deployment completed"
}

# Blue-green deployment
blue_green_deploy() {
    local env=$1
    local host=$2
    local user=$3
    
    log_info "Starting blue-green deployment..."
    
    # Determine current color
    local current_color=$(ssh -i ${DEPLOY_KEY} ${user}@${host} "docker-compose ps | grep -o 'blue\\|green' | head -1")
    local new_color=$([ "$current_color" = "blue" ] && echo "green" || echo "blue")
    
    log_info "Current color: $current_color, New color: $new_color"
    
    # Deploy to new color
    ssh -i ${DEPLOY_KEY} ${user}@${host} << ENDSSH
        cd /opt/${PROJECT_NAME}
        
        # Deploy to new color
        docker-compose -f docker-compose.${new_color}.yml up -d
        
        # Wait for new deployment to be ready
        sleep 60
        
        # Health check new deployment
        curl -f http://localhost:${new_color}/healthz || exit 1
        
        # Switch traffic to new color
        docker-compose exec nginx nginx -s reload
        
        # Stop old color
        docker-compose -f docker-compose.${current_color}.yml down
        
        # Clean up old images
        docker image prune -f
ENDSSH
    
    log_success "Blue-green deployment completed"
}

# Main deployment function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Memoria AI Deployment                     ║"
    echo "║              AI-Powered Memory System                        ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    case "${1:-}" in
        staging)
            deploy_staging
            ;;
        production)
            deploy_production
            ;;
        rollback-staging)
            rollback "staging" "${STAGING_HOST}" "${STAGING_USER}"
            ;;
        rollback-production)
            rollback "production" "${PRODUCTION_HOST}" "${PRODUCTION_USER}"
            ;;
        blue-green-staging)
            blue_green_deploy "staging" "${STAGING_HOST}" "${STAGING_USER}"
            ;;
        blue-green-production)
            blue_green_deploy "production" "${PRODUCTION_HOST}" "${PRODUCTION_USER}"
            ;;
        *)
            echo "Usage: $0 {staging|production|rollback-staging|rollback-production|blue-green-staging|blue-green-production}"
            exit 1
            ;;
    esac
}

# Handle script arguments
main "$@"