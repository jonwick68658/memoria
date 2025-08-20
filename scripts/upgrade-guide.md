# Memoria AI Upgrade Guide

## Overview

This guide provides comprehensive instructions for safely upgrading your Memoria AI installation with zero downtime and automatic rollback capabilities.

## Quick Start

```bash
# Run full upgrade with all safety checks
./scripts/upgrade.sh

# Or with specific options
BACKUP_DIR=/custom/backups ./scripts/upgrade.sh --upgrade
```

## Upgrade Process

### 1. Pre-Upgrade Checks
- **System Resources**: Verifies disk space (>15% free) and memory (>10% free)
- **Docker Health**: Ensures Docker and Docker Compose are available
- **Service Status**: Confirms all services are running properly

### 2. Backup Creation
- **Database**: Full PostgreSQL backup with compression
- **Configuration**: Environment files and Docker Compose
- **Volumes**: Complete data volumes (PostgreSQL, Redis, Weaviate)
- **Application Data**: All persistent storage

### 3. Image Updates
- **Pull Latest**: Downloads new Docker images
- **Registry Support**: Custom registry configuration
- **Tag Selection**: Specific image tags or latest

### 4. Testing
- **Unit Tests**: Complete test suite execution
- **Integration Tests**: End-to-end functionality
- **Health Checks**: Service availability verification

### 5. Service Updates
- **Graceful Shutdown**: Zero-downtime service stop
- **Configuration Updates**: Apply new settings
- **Service Start**: Sequential service startup

### 6. Post-Upgrade Validation
- **Health Checks**: Comprehensive service verification
- **API Tests**: Endpoint functionality
- **Database Integrity**: Data consistency checks

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKUP_DIR` | `./backups/pre-upgrade` | Backup storage location |
| `UPGRADE_LOG` | `./logs/upgrade.log` | Upgrade process log |
| `ROLLBACK_ENABLED` | `true` | Enable automatic rollback |
| `HEALTH_CHECK_TIMEOUT` | `300` | Health check timeout (seconds) |
| `BACKUP_TIMEOUT` | `600` | Backup timeout (seconds) |
| `DOCKER_REGISTRY` | `` | Custom Docker registry URL |
| `IMAGE_TAG` | `latest` | Docker image tag |
| `SKIP_TESTS` | `false` | Skip test execution |
| `SKIP_BACKUP` | `false` | Skip backup creation |
| `FORCE_UPGRADE` | `false` | Force upgrade without prompts |

### Command Line Options

```bash
# Show help
./scripts/upgrade.sh --help

# Run specific steps
./scripts/upgrade.sh --check      # Pre-upgrade checks only
./scripts/upgrade.sh --backup     # Create backup only
./scripts/upgrade.sh --test       # Run tests only
./scripts/upgrade.sh --report     # Generate upgrade report

# Force upgrade
FORCE_UPGRADE=true ./scripts/upgrade.sh --upgrade
```

## Rollback Process

### Automatic Rollback
If any step fails and `ROLLBACK_ENABLED=true`, the system automatically:
1. Stops new services
2. Restores previous configuration
3. Restarts services with old images
4. Verifies system health

### Manual Rollback
```bash
# Rollback to previous version
./scripts/upgrade.sh --rollback

# Or use restore script
./scripts/restore.sh --restore
```

## Backup Management

### Backup Locations
- **Default**: `./backups/pre-upgrade/`
- **Custom**: Set `BACKUP_DIR` environment variable
- **Structure**:
  ```
  backups/
  ├── pre-upgrade/
  │   ├── database_backup_YYYYMMDD_HHMMSS.sql.gz
  │   ├── postgres_data_backup_YYYYMMDD_HHMMSS.tar.gz
  │   ├── redis_data_backup_YYYYMMDD_HHMMSS.tar.gz
  │   ├── weaviate_data_backup_YYYYMMDD_HHMMSS.tar.gz
  │   ├── env_backup_YYYYMMDD_HHMMSS
  │   └── docker-compose_backup_YYYYMMDD_HHMMSS
  ```

### Backup Retention
- **Automatic**: Keeps last 10 backups
- **Manual**: Use `./scripts/backup.sh --cleanup` for cleanup

## Monitoring and Alerts

### Health Checks
```bash
# Check system health
./scripts/health-check.sh --once

# Continuous monitoring
./scripts/monitor.sh --health
```

### Log Monitoring
```bash
# Real-time upgrade logs
tail -f logs/upgrade.log

# Service logs
docker-compose logs -f
```

## Troubleshooting

### Common Issues

#### Insufficient Disk Space
```bash
# Check disk usage
df -h

# Clean up old backups
./scripts/backup.sh --cleanup --keep 5

# Or use custom backup location
BACKUP_DIR=/mnt/large-disk/backups ./scripts/upgrade.sh
```

#### Docker Registry Issues
```bash
# Use specific registry
DOCKER_REGISTRY=registry.company.com ./scripts/upgrade.sh

# Or skip image pull
SKIP_TESTS=true ./scripts/upgrade.sh --upgrade
```

#### Service Startup Failures
```bash
# Check service logs
docker-compose logs memoria-api
docker-compose logs postgres
docker-compose logs redis

# Manual rollback
./scripts/restore.sh --restore
```

### Debug Mode
```bash
# Enable debug logging
DEBUG=true ./scripts/upgrade.sh --upgrade

# Verbose output
./scripts/upgrade.sh --upgrade 2>&1 | tee upgrade-debug.log
```

## Advanced Usage

### Custom Registry
```bash
# Private registry
DOCKER_REGISTRY=my-registry.com/memoria \
IMAGE_TAG=v2.1.0 \
./scripts/upgrade.sh --upgrade
```

### Staged Upgrade
```bash
# Step 1: Create backup
./scripts/upgrade.sh --backup

# Step 2: Test on staging
./scripts/upgrade.sh --test

# Step 3: Deploy to production
./scripts/upgrade.sh --upgrade
```

### Zero-Downtime Upgrade
```bash
# Blue-green deployment
./scripts/upgrade.sh --upgrade --blue-green

# Rolling update
./scripts/upgrade.sh --upgrade --rolling
```

## Integration with CI/CD

### GitHub Actions
```yaml
- name: Upgrade Memoria AI
  run: |
    ./scripts/upgrade.sh --upgrade
  env:
    BACKUP_DIR: /tmp/backups
    SKIP_TESTS: false
```

### Jenkins Pipeline
```groovy
stage('Upgrade') {
    steps {
        script {
            env.BACKUP_DIR = '/opt/backups'
            sh './scripts/upgrade.sh --upgrade'
        }
    }
}
```

## Security Considerations

### Backup Encryption
```bash
# Encrypt backups
BACKUP_ENCRYPT=true ./scripts/upgrade.sh --backup

# Decrypt during restore
BACKUP_DECRYPT=true ./scripts/restore.sh --restore
```

### Access Control
- **Backup Directory**: Ensure proper permissions (700)
- **Log Files**: Restrict access to upgrade logs
- **Registry**: Use authenticated registry access

## Performance Optimization

### Resource Planning
- **Minimum Requirements**: 4GB RAM, 20GB disk space
- **Recommended**: 8GB RAM, 50GB disk space
- **Production**: 16GB RAM, 100GB disk space

### Network Optimization
- **Registry Mirror**: Configure Docker registry mirror
- **Parallel Downloads**: Enable parallel image pulls
- **Bandwidth**: Ensure stable internet connection

## Support and Maintenance

### Regular Maintenance
```bash
# Weekly backup
./scripts/backup.sh --backup

# Monthly upgrade check
./scripts/upgrade.sh --check

# Quarterly full upgrade
./scripts/upgrade.sh --upgrade
```

### Support Resources
- **Documentation**: Check `docs/` directory
- **Logs**: Review `logs/upgrade.log`
- **Community**: GitHub issues and discussions
- **Professional**: Contact support@memoria-ai.com

## Best Practices

### Pre-Upgrade Checklist
- [ ] Review changelog and breaking changes
- [ ] Schedule maintenance window
- [ ] Notify users of potential downtime
- [ ] Verify backup storage space
- [ ] Test upgrade in staging environment
- [ ] Prepare rollback plan

### Post-Upgrade Checklist
- [ ] Verify all services are running
- [ ] Check application functionality
- [ ] Monitor system resources
- [ ] Review logs for errors
- [ ] Update documentation
- [ ] Notify users of completion

### Emergency Procedures
- **Immediate Rollback**: `./scripts/restore.sh --restore`
- **Service Restart**: `docker-compose restart`
- **Log Analysis**: `docker-compose logs --tail=100`
- **Health Check**: `./scripts/health-check.sh --once`