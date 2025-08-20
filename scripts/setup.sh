#!/bin/bash
# Memoria AI Setup Script
# This script sets up the complete Memoria AI system

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
PROJECT_NAME="Memoria AI"
REQUIRED_TOOLS=("docker" "docker-compose" "python3" "pip" "git")
PYTHON_VERSION="3.8"

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    for tool in "${REQUIRED_TOOLS[@]}"; do
        if ! command_exists "$tool"; then
            log_error "$tool is required but not installed"
            exit 1
        fi
        log_success "$tool is available"
    done
    
    # Check Python version
    PYTHON_VER=$(python3 --version 2>&1 | awk '{print $2}')
    if [[ "$(printf '%s\n' "$PYTHON_VERSION" "$PYTHON_VER" | sort -V | head -n1)" != "$PYTHON_VERSION" ]]; then
        log_error "Python $PYTHON_VERSION or higher is required (found $PYTHON_VER)"
        exit 1
    fi
    log_success "Python version check passed"
}

# Create environment file
setup_environment() {
    log_info "Setting up environment configuration..."
    
    if [ ! -f .env ]; then
        cp .env.example .env
        log_success "Created .env file from .env.example"
        log_warning "Please edit .env file with your actual configuration values"
    else
        log_info ".env file already exists"
    fi
    
    # Create logs directory
    mkdir -p logs
    log_success "Created logs directory"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_success "Created virtual environment"
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install dependencies
    pip install -e .[dev,all]
    
    log_success "Python dependencies installed"
}

# Setup Docker environment
setup_docker() {
    log_info "Setting up Docker environment..."
    
    # Pull required images
    docker-compose pull
    
    # Build custom images
    docker-compose build
    
    log_success "Docker environment ready"
}

# Initialize database
init_database() {
    log_info "Initializing database..."
    
    # Start database services
    docker-compose up -d postgres redis
    
    # Wait for services to be ready
    log_info "Waiting for database to be ready..."
    sleep 10
    
    # Run migrations
    docker-compose run --rm memoria-api alembic upgrade head
    
    log_success "Database initialized"
}

# Setup pre-commit hooks
setup_git_hooks() {
    log_info "Setting up Git hooks..."
    
    if [ -d ".git" ]; then
        source venv/bin/activate
        pre-commit install
        pre-commit install --hook-type commit-msg
        log_success "Git hooks installed"
    else
        log_warning "Not in a Git repository, skipping Git hooks setup"
    fi
}

# Run initial tests
run_tests() {
    log_info "Running initial tests..."
    
    source venv/bin/activate
    
    # Run unit tests
    pytest tests/ -v --tb=short
    
    # Run integration test
    python test_integration.py
    
    log_success "Initial tests passed"
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    
    mkdir -p {logs,backups,uploads,temp,ssl,docs/_build}
    log_success "Directories created"
}

# Setup monitoring
setup_monitoring() {
    log_info "Setting up monitoring..."
    
    # Start monitoring services
    docker-compose up -d prometheus grafana
    
    log_success "Monitoring services started"
    log_info "Grafana available at: http://localhost:3000 (admin/admin123)"
    log_info "Prometheus available at: http://localhost:9090"
}

# Main setup function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Memoria AI Setup                          ║"
    echo "║              AI-Powered Memory System                        ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    check_requirements
    create_directories
    setup_environment
    install_python_deps
    setup_docker
    init_database
    setup_git_hooks
    setup_monitoring
    
    log_success "Setup complete! 🎉"
    echo ""
    echo "Next steps:"
    echo "1. Edit .env file with your API keys and configuration"
    echo "2. Run 'make quick-start' to start all services"
    echo "3. Visit http://localhost:8000/docs for API documentation"
    echo "4. Visit http://localhost:5555 for task monitoring (Flower)"
    echo "5. Visit http://localhost:3000 for monitoring (Grafana)"
    echo ""
    echo "Quick commands:"
    echo "  make up          - Start all services"
    echo "  make down        - Stop all services"
    echo "  make test        - Run tests"
    echo "  make logs        - View logs"
    echo ""
    log_info "For more commands, run: make help"
}

# Handle script arguments
case "${1:-}" in
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --skip-tests   Skip running tests"
        echo "  --skip-docker  Skip Docker setup"
        echo "  --minimal      Minimal setup (no monitoring)"
        exit 0
        ;;
    --skip-tests)
        SKIP_TESTS=true
        ;;
    --skip-docker)
        SKIP_DOCKER=true
        ;;
    --minimal)
        MINIMAL_SETUP=true
        ;;
esac

# Run main function
main