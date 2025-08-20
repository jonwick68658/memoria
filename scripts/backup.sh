#!/bin/bash
# Memoria AI Backup Script
# Comprehensive backup solution for database, files, and configurations

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="memoria-ai"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
S3_BUCKET="${S3_BUCKET:-}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-memoria-postgres-1}"
POSTGRES_USER="${POSTGRES_USER:-memoria}"
POSTGRES_DB="${POSTGRES_DB:-memoria_db}"
ENCRYPTION_KEY="${ENCRYPTION_KEY:-}"

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

# Create backup directory
create_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        log_success "Created backup directory: $BACKUP_DIR"
    fi
}

# Generate backup filename
generate_filename() {
    local prefix=$1
    local timestamp=$(date +%Y%m%d_%H%M%S)
    echo "${prefix}_${timestamp}"
}

# Backup PostgreSQL database
backup_database() {
    local backup_name=$(generate_filename "database")
    local backup_file="${BACKUP_DIR}/${backup_name}.sql"
    
    log_info "Starting database backup..."
    
    # Create database backup
    docker exec "$POSTGRES_CONTAINER" pg_dump \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        --verbose \
        --clean \
        --if-exists \
        --no-owner \
        --no-privileges \
        > "$backup_file"
    
    # Compress backup
    gzip "$backup_file"
    local compressed_file="${backup_file}.gz"
    
    # Calculate checksum
    local checksum=$(sha256sum "$compressed_file" | cut -d' ' -f1)
    echo "$checksum" > "${compressed_file}.sha256"
    
    log_success "Database backup created: $(basename $compressed_file)"
    echo "$compressed_file"
}

# Backup uploaded files
backup_files() {
    local backup_name=$(generate_filename "files")
    local backup_file="${BACKUP_DIR}/${backup_name}.tar.gz"
    
    log_info "Starting files backup..."
    
    # Create archive of uploaded files
    if [ -d "uploads" ]; then
        tar -czf "$backup_file" uploads/
        
        # Calculate checksum
        local checksum=$(sha256sum "$backup_file" | cut -d' ' -f1)
        echo "$checksum" > "${backup_file}.sha256"
        
        log_success "Files backup created: $(basename $backup_file)"
        echo "$backup_file"
    else
        log_warning "No uploads directory found, skipping files backup"
    fi
}

# Backup configuration files
backup_config() {
    local backup_name=$(generate_filename "config")
    local backup_file="${BACKUP_DIR}/${backup_name}.tar.gz"
    
    log_info "Starting configuration backup..."
    
    # Create archive of configuration files
    tar -czf "$backup_file" \
        .env \
        docker-compose.yml \
        requirements.txt \
        app/ \
        scripts/ \
        --exclude='*.pyc' \
        --exclude='__pycache__' \
        --exclude='.git'
    
    # Calculate checksum
    local checksum=$(sha256sum "$backup_file" | cut -d' ' -f1)
    echo "$checksum" > "${backup_file}.sha256"
    
    log_success "Configuration backup created: $(basename $backup_file)"
    echo "$backup_file"
}

# Encrypt backup files
encrypt_backup() {
    local file=$1
    
    if [ -n "$ENCRYPTION_KEY" ]; then
        log_info "Encrypting backup file..."
        
        local encrypted_file="${file}.enc"
        openssl enc -aes-256-cbc -salt -in "$file" -out "$encrypted_file" -k "$ENCRYPTION_KEY"
        
        # Remove unencrypted file
        rm "$file"
        
        log_success "Backup encrypted: $(basename $encrypted_file)"
        echo "$encrypted_file"
    else
        log_warning "No encryption key provided, skipping encryption"
        echo "$file"
    fi
}

# Upload to S3
upload_to_s3() {
    local file=$1
    
    if [ -n "$S3_BUCKET" ] && command -v aws >/dev/null 2>&1; then
        log_info "Uploading to S3..."
        
        local filename=$(basename "$file")
        aws s3 cp "$file" "s3://${S3_BUCKET}/backups/${filename}"
        
        # Upload checksum
        aws s3 cp "${file}.sha256" "s3://${S3_BUCKET}/backups/${filename}.sha256"
        
        log_success "Uploaded to S3: s3://${S3_BUCKET}/backups/${filename}"
    else
        log_warning "S3 upload skipped (no bucket configured or AWS CLI not available)"
    fi
}

# Clean old backups
clean_old_backups() {
    log_info "Cleaning old backups..."
    
    # Local cleanup
    find "$BACKUP_DIR" -name "*.sql.gz" -type f -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR" -name "*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR" -name "*.sha256" -type f -mtime +$RETENTION_DAYS -delete
    
    # S3 cleanup
    if [ -n "$S3_BUCKET" ] && command -v aws >/dev/null 2>&1; then
        aws s3 ls "s3://${S3_BUCKET}/backups/" | \
            awk '{print $4}' | \
            while read -r file; do
                local file_date=$(echo "$file" | grep -o '[0-9]\{8\}' | head -1)
                local file_age=$(( ($(date +%s) - $(date -d "$file_date" +%s)) / 86400 ))
                
                if [ "$file_age" -gt "$RETENTION_DAYS" ]; then
                    aws s3 rm "s3://${S3_BUCKET}/backups/$file"
                    log_info "Deleted old S3 backup: $file"
                fi
            done
    fi
    
    log_success "Old backups cleaned"
}

# Verify backup integrity
verify_backup() {
    local file=$1
    
    log_info "Verifying backup integrity..."
    
    # Check if file exists
    if [ ! -f "$file" ]; then
        log_error "Backup file not found: $file"
        return 1
    fi
    
    # Verify checksum
    if [ -f "${file}.sha256" ]; then
        local expected_checksum=$(cat "${file}.sha256")
        local actual_checksum=$(sha256sum "$file" | cut -d' ' -f1)
        
        if [ "$expected_checksum" = "$actual_checksum" ]; then
            log_success "Backup integrity verified"
            return 0
        else
            log_error "Backup integrity check failed"
            return 1
        fi
    else
        log_warning "No checksum file found, skipping integrity check"
        return 0
    fi
}

# Restore from backup
restore_backup() {
    local backup_file=$1
    local restore_type=$2
    
    log_info "Starting restore from backup: $(basename $backup_file)"
    
    # Verify backup before restore
    verify_backup "$backup_file" || {
        log_error "Backup verification failed, aborting restore"
        return 1
    }
    
    case "$restore_type" in
        database)
            restore_database "$backup_file"
            ;;
        files)
            restore_files "$backup_file"
            ;;
        config)
            restore_config "$backup_file"
            ;;
        *)
            log_error "Invalid restore type: $restore_type"
            return 1
            ;;
    esac
}

# Restore database
restore_database() {
    local backup_file=$1
    
    log_info "Restoring database from backup..."
    
    # Decrypt if necessary
    local restore_file="$backup_file"
    if [[ "$backup_file" == *.enc ]]; then
        restore_file="${backup_file%.enc}"
        openssl enc -aes-256-cbc -d -in "$backup_file" -out "$restore_file" -k "$ENCRYPTION_KEY"
    fi
    
    # Decompress if necessary
    if [[ "$restore_file" == *.gz ]]; then
        gunzip "$restore_file"
        restore_file="${restore_file%.gz}"
    fi
    
    # Stop application services
    docker-compose stop memoria-api
    
    # Restore database
    docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$restore_file"
    
    # Start application services
    docker-compose start memoria-api
    
    log_success "Database restored successfully"
}

# Restore files
restore_files() {
    local backup_file=$1
    
    log_info "Restoring files from backup..."
    
    # Decrypt if necessary
    local restore_file="$backup_file"
    if [[ "$backup_file" == *.enc ]]; then
        restore_file="${backup_file%.enc}"
        openssl enc -aes-256-cbc -d -in "$backup_file" -out "$restore_file" -k "$ENCRYPTION_KEY"
    fi
    
    # Extract files
    tar -xzf "$restore_file"
    
    log_success "Files restored successfully"
}

# Restore configuration
restore_config() {
    local backup_file=$1
    
    log_info "Restoring configuration from backup..."
    
    # Decrypt if necessary
    local restore_file="$backup_file"
    if [[ "$backup_file" == *.enc ]]; then
        restore_file="${backup_file%.enc}"
        openssl enc -aes-256-cbc -d -in "$backup_file" -out "$restore_file" -k "$ENCRYPTION_KEY"
    fi
    
    # Extract configuration
    tar -xzf "$restore_file"
    
    log_success "Configuration restored successfully"
}

# List available backups
list_backups() {
    log_info "Available backups:"
    
    if [ -d "$BACKUP_DIR" ]; then
        ls -la "$BACKUP_DIR" | grep -E '\.(sql\.gz|tar\.gz|enc)$'
    else
        log_warning "No backup directory found"
    fi
}

# Main backup function
run_backup() {
    log_info "Starting comprehensive backup..."
    
    create_backup_dir
    
    local backup_files=()
    
    # Backup database
    local db_backup=$(backup_database)
    if [ -n "$db_backup" ]; then
        backup_files+=("$db_backup")
    fi
    
    # Backup files
    local files_backup=$(backup_files)
    if [ -n "$files_backup" ]; then
        backup_files+=("$files_backup")
    fi
    
    # Backup configuration
    local config_backup=$(backup_config)
    if [ -n "$config_backup" ]; then
        backup_files+=("$config_backup")
    fi
    
    # Encrypt backups
    for file in "${backup_files[@]}"; do
        encrypt_backup "$file"
    done
    
    # Upload to S3
    for file in "${backup_files[@]}"; do
        upload_to_s3 "$file"
    done
    
    # Clean old backups
    clean_old_backups
    
    log_success "Backup completed successfully!"
}

# Main function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Memoria AI Backup System                  ║"
    echo "║              Comprehensive Backup & Restore                  ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    case "${1:-}" in
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --help, -h         Show this help message"
            echo "  --backup           Run full backup"
            echo "  --restore FILE     Restore from backup file"
            echo "  --list             List available backups"
            echo "  --verify FILE      Verify backup integrity"
            echo "  --database         Backup only database"
            echo "  --files            Backup only files"
            echo "  --config           Backup only configuration"
            echo ""
            echo "Environment variables:"
            echo "  BACKUP_DIR         Backup directory (default: ./backups)"
            echo "  RETENTION_DAYS     Days to keep backups (default: 30)"
            echo "  S3_BUCKET          S3 bucket for remote storage"
            echo "  ENCRYPTION_KEY     Key for backup encryption"
            exit 0
            ;;
        --backup)
            run_backup
            ;;
        --restore)
            if [ -z "$2" ]; then
                log_error "Backup file required for restore"
                exit 1
            fi
            restore_backup "$2" "$3"
            ;;
        --list)
            list_backups
            ;;
        --verify)
            if [ -z "$2" ]; then
                log_error "Backup file required for verification"
                exit 1
            fi
            verify_backup "$2"
            ;;
        --database)
            create_backup_dir
            backup_database
            ;;
        --files)
            create_backup_dir
            backup_files
            ;;
        --config)
            create_backup_dir
            backup_config
            ;;
        *)
            run_backup
            ;;
    esac
}

# Handle script arguments
main "$@"