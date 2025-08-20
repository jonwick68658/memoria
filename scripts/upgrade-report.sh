#!/bin/bash
# Memoria AI Upgrade Report Generator
# Generates comprehensive upgrade reports with metrics and recommendations

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
REPORT_DIR="${REPORT_DIR:-./reports}"
UPGRADE_LOG="${UPGRADE_LOG:-./logs/upgrade.log}"
TEST_REPORT="${TEST_REPORT:-./reports/upgrade-test-report.json}"
SYSTEM_INFO="${SYSTEM_INFO:-./reports/system-info.json}"
METRICS_FILE="${METRICS_FILE:-./reports/upgrade-metrics.json}"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
REPORT_FILE="${REPORT_FILE:-$REPORT_DIR/upgrade-report_$TIMESTAMP.html}"

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

# Create report directory
create_report_dir() {
    mkdir -p "$REPORT_DIR"
}

# Collect system information
collect_system_info() {
    log_info "Collecting system information..."
    
    cat > "$SYSTEM_INFO" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "hostname": "$(hostname)",
    "os": {
        "name": "$(uname -s)",
        "kernel": "$(uname -r)",
        "architecture": "$(uname -m)"
    },
    "docker": {
        "version": "$(docker --version 2>/dev/null || echo 'not available')",
        "compose_version": "$(docker-compose --version 2>/dev/null || echo 'not available')",
        "running_containers": $(docker ps --format json | wc -l),
        "total_containers": $(docker ps -a --format json | wc -l)
    },
    "system": {
        "cpu_cores": $(nproc),
        "memory_gb": $(free -g | awk '/^Mem:/ {print $2}'),
        "disk_usage": "$(df -h / | awk 'NR==2 {print $5}')",
        "uptime": "$(uptime -p)"
    }
}
EOF
}

# Collect upgrade metrics
collect_upgrade_metrics() {
    log_info "Collecting upgrade metrics..."
    
    local upgrade_start=$(grep -m1 "Starting upgrade process" "$UPGRADE_LOG" | cut -d' ' -f1-2 || echo "")
    local upgrade_end=$(grep -m1 "Upgrade process completed" "$UPGRADE_LOG" | cut -d' ' -f1-2 || echo "")
    
    local duration=0
    if [ -n "$upgrade_start" ] && [ -n "$upgrade_end" ]; then
        duration=$(date -d "$upgrade_end" +%s 2>/dev/null || echo 0)
        local start_ts=$(date -d "$upgrade_start" +%s 2>/dev/null || echo 0)
        if [ $duration -gt 0 ] && [ $start_ts -gt 0 ]; then
            duration=$((duration - start_ts))
        fi
    fi
    
    local backup_size=$(du -sh ./backups/pre-upgrade 2>/dev/null | cut -f1 || echo "0")
    local log_size=$(du -sh "$UPGRADE_LOG" 2>/dev/null | cut -f1 || echo "0")
    
    cat > "$METRICS_FILE" << EOF
{
    "upgrade": {
        "start_time": "$upgrade_start",
        "end_time": "$upgrade_end",
        "duration_seconds": $duration,
        "status": "$(grep -m1 "Upgrade process completed" "$UPGRADE_LOG" | grep -o 'successfully\|failed' || echo 'unknown')"
    },
    "backup": {
        "size": "$backup_size",
        "location": "./backups/pre-upgrade",
        "created": "$(ls -la ./backups/pre-upgrade/ 2>/dev/null | head -2 | tail -1 | awk '{print $6, $7, $8}' || echo 'not found')"
    },
    "logs": {
        "size": "$log_size",
        "location": "$UPGRADE_LOG",
        "errors": $(grep -c "ERROR" "$UPGRADE_LOG" 2>/dev/null || echo 0),
        "warnings": $(grep -c "WARNING" "$UPGRADE_LOG" 2>/dev/null || echo 0)
    },
    "services": {
        "api": "$(docker inspect --format='{{.State.Status}}' memoria-api-1 2>/dev/null || echo 'not found')",
        "postgres": "$(docker inspect --format='{{.State.Status}}' memoria-postgres-1 2>/dev/null || echo 'not found')",
        "redis": "$(docker inspect --format='{{.State.Status}}' memoria-redis-1 2>/dev/null || echo 'not found')",
        "weaviate": "$(docker inspect --format='{{.State.Status}}' memoria-weaviate-1 2>/dev/null || echo 'not found')"
    }
}
EOF
}

# Generate HTML report
generate_html_report() {
    log_info "Generating HTML report..."
    
    local test_data=""
    if [ -f "$TEST_REPORT" ]; then
        test_data=$(cat "$TEST_REPORT")
    else
        test_data='{"summary": {"total_tests": 0, "passed": 0, "failed": 0, "skipped": 0, "pass_rate": 0}}'
    fi
    
    local system_data=""
    if [ -f "$SYSTEM_INFO" ]; then
        system_data=$(cat "$SYSTEM_INFO")
    else
        system_data='{"os": {"name": "unknown"}, "docker": {"version": "unknown"}}'
    fi
    
    local metrics_data=""
    if [ -f "$METRICS_FILE" ]; then
        metrics_data=$(cat "$METRICS_FILE")
    else
        metrics_data='{"upgrade": {"duration_seconds": 0, "status": "unknown"}}'
    fi
    
    cat > "$REPORT_FILE" << EOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Memoria AI Upgrade Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }
        .header p {
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }
        .section {
            padding: 30px;
            border-bottom: 1px solid #eee;
        }
        .section:last-child {
            border-bottom: none;
        }
        .section h2 {
            margin-top: 0;
            color: #667eea;
            font-size: 1.8em;
            font-weight: 400;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .card {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            border-left: 4px solid #667eea;
        }
        .card h3 {
            margin-top: 0;
            color: #333;
            font-size: 1.2em;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        .metric:last-child {
            border-bottom: none;
        }
        .metric-label {
            font-weight: 500;
            color: #555;
        }
        .metric-value {
            font-weight: 600;
            color: #333;
        }
        .status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 500;
        }
        .status.success {
            background: #d4edda;
            color: #155724;
        }
        .status.warning {
            background: #fff3cd;
            color: #856404;
        }
        .status.error {
            background: #f8d7da;
            color: #721c24;
        }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e9ecef;
            border-radius: 4px;
            overflow: hidden;
            margin: 10px 0;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s ease;
        }
        .log-section {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
        }
        .log-entry {
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            padding: 5px 0;
            border-bottom: 1px solid #eee;
        }
        .log-entry:last-child {
            border-bottom: none;
        }
        .log-entry.error {
            color: #dc3545;
        }
        .log-entry.warning {
            color: #ffc107;
        }
        .log-entry.info {
            color: #007bff;
        }
        .recommendations {
            background: #e7f3ff;
            border-left: 4px solid #007bff;
            padding: 20px;
            border-radius: 4px;
            margin-top: 20px;
        }
        .recommendations h4 {
            margin-top: 0;
            color: #007bff;
        }
        .recommendations ul {
            margin: 10px 0;
            padding-left: 20px;
        }
        .recommendations li {
            margin: 5px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Memoria AI Upgrade Report</h1>
            <p>Comprehensive upgrade analysis and validation report</p>
            <p><strong>Generated:</strong> $(date '+%B %d, %Y at %I:%M %p')</p>
        </div>

        <div class="section">
            <h2>Executive Summary</h2>
            <div class="grid">
                <div class="card">
                    <h3>Upgrade Status</h3>
                    <div class="metric">
                        <span class="metric-label">Status:</span>
                        <span class="metric-value">
                            <span class="status $(echo "$metrics_data" | jq -r '.upgrade.status // "unknown"' | sed 's/successfully/success/; s/failed/error/; s/unknown/warning/')">
                                $(echo "$metrics_data" | jq -r '.upgrade.status // "Unknown"')
                            </span>
                        </span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Duration:</span>
                        <span class="metric-value">$(echo "$metrics_data" | jq -r '.upgrade.duration_seconds // 0') seconds</span>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Test Results</h3>
                    <div class="metric">
                        <span class="metric-label">Total Tests:</span>
                        <span class="metric-value">$(echo "$test_data" | jq -r '.summary.total_tests // 0')</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Pass Rate:</span>
                        <span class="metric-value">$(echo "$test_data" | jq -r '.summary.pass_rate // 0')%</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: $(echo "$test_data" | jq -r '.summary.pass_rate // 0')%"></div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>System Information</h3>
                    <div class="metric">
                        <span class="metric-label">OS:</span>
                        <span class="metric-value">$(echo "$system_data" | jq -r '.os.name // "Unknown"')</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Docker:</span>
                        <span class="metric-value">$(echo "$system_data" | jq -r '.docker.version // "Unknown"')</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Containers:</span>
                        <span class="metric-value">$(echo "$system_data" | jq -r '.docker.running_containers // 0') running</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Service Status</h2>
            <div class="grid">
                <div class="card">
                    <h3>API Service</h3>
                    <div class="metric">
                        <span class="metric-label">Status:</span>
                        <span class="metric-value">
                            <span class="status $(echo "$metrics_data" | jq -r '.services.api // "unknown"' | sed 's/running/success/; s/exited/error/; s/restarting/warning/')">
                                $(echo "$metrics_data" | jq -r '.services.api // "Unknown"')
                            </span>
                        </span>
                    </div>
                </div>
                
                <div class="card">
                    <h3>PostgreSQL</h3>
                    <div class="metric">
                        <span class="metric-label">Status:</span>
                        <span class="metric-value">
                            <span class="status $(echo "$metrics_data" | jq -r '.services.postgres // "unknown"' | sed 's/running/success/; s/exited/error/; s/restarting/warning/')">
                                $(echo "$metrics_data" | jq -r '.services.postgres // "Unknown"')
                            </span>
                        </span>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Redis</h3>
                    <div class="metric">
                        <span class="metric-label">Status:</span>
                        <span class="metric-value">
                            <span class="status $(echo "$metrics_data" | jq -r '.services.redis // "unknown"' | sed 's/running/success/; s/exited/error/; s/restarting/warning/')">
                                $(echo "$metrics_data" | jq -r '.services.redis // "Unknown"')
                            </span>
                        </span>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Weaviate</h3>
                    <div class="metric">
                        <span class="metric-label">Status:</span>
                        <span class="metric-value">
                            <span class="status $(echo "$metrics_data" | jq -r '.services.weaviate // "unknown"' | sed 's/running/success/; s/exited/error/; s/restarting/warning/')">
                                $(echo "$metrics_data" | jq -r '.services.weaviate // "Unknown"')
                            </span>
                        </span>
                    </div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Backup Information</h2>
            <div class="grid">
                <div class="card">
                    <h3>Backup Details</h3>
                    <div class="metric">
                        <span class="metric-label">Size:</span>
                        <span class="metric-value">$(echo "$metrics_data" | jq -r '.backup.size // "0"')</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Location:</span>
                        <span class="metric-value">$(echo "$metrics_data" | jq -r '.backup.location // "./backups/pre-upgrade"')</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Created:</span>
                        <span class="metric-value">$(echo "$metrics_data" | jq -r '.backup.created // "Unknown"')</span>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Log Analysis</h3>
                    <div class="metric">
                        <span class="metric-label">Log Size:</span>
                        <span class="metric-value">$(echo "$metrics_data" | jq -r '.logs.size // "0"')</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Errors:</span>
                        <span class="metric-value">$(echo "$metrics_data" | jq -r '.logs.errors // 0')</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Warnings:</span>
                        <span class="metric-value">$(echo "$metrics_data" | jq -r '.logs.warnings // 0')</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Test Results</h2>
            <div class="grid">
                <div class="card">
                    <h3>Test Summary</h3>
                    <div class="metric">
                        <span class="metric-label">Total Tests:</span>
                        <span class="metric-value">$(echo "$test_data" | jq -r '.summary.total_tests // 0')</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Passed:</span>
                        <span class="metric-value">$(echo "$test_data" | jq -r '.summary.passed // 0')</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Failed:</span>
                        <span class="metric-value">$(echo "$test_data" | jq -r '.summary.failed // 0')</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Skipped:</span>
                        <span class="metric-value">$(echo "$test_data" | jq -r '.summary.skipped // 0')</span>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Detailed Test Results</h3>
                    <div id="test-results">
                        Loading test results...
                    </div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Recent Log Entries</h2>
            <div class="log-section">
                <h3>Upgrade Log (Last 20 entries)</h3>
                <div id="log-entries">
                    Loading log entries...
                </div>
            </div>
        </div>

        <div class="section">
            <h2>Recommendations</h2>
            <div class="recommendations">
                <h4>Based on this upgrade analysis:</h4>
                <ul>
                    <li>Monitor system resources for the next 24 hours</li>
                    <li>Review application logs for any anomalies</li>
                    <li>Verify backup integrity and retention policies</li>
                    <li>Consider implementing automated health checks</li>
                    <li>Schedule regular maintenance windows for future upgrades</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        // Load test results
        const testData = $(echo "$test_data" | jq -c '.');
        const testResultsDiv = document.getElementById('test-results');
        
        if (testData.tests && Object.keys(testData.tests).length > 0) {
            let html = '<div class="metric">';
            Object.entries(testData.tests).forEach(([testName, result]) => {
                const statusClass = result.status.toLowerCase();
                html += \`
                    <div class="metric">
                        <span class="metric-label">\${testName}:</span>
                        <span class="metric-value">
                            <span class="status \${statusClass}">\${result.status}</span>
                            (\${result.duration}s)
                        </span>
                    </div>
                \`;
            });
            html += '</div>';
            testResultsDiv.innerHTML = html;
        } else {
            testResultsDiv.innerHTML = '<p>No test results available</p>';
        }

        // Load log entries
        fetch('data:text/plain;base64,$(tail -20 "$UPGRADE_LOG" | base64 -w 0)')
            .then(response => response.text())
            .then(text => {
                const logEntries = text.split('\\n').filter(line => line.trim());
                const logDiv = document.getElementById('log-entries');
                logDiv.innerHTML = logEntries.map(entry => {
                    const className = entry.includes('ERROR') ? 'error' : 
                                    entry.includes('WARNING') ? 'warning' : 'info';
                    return \`<div class="log-entry \${className}">\${entry}</div>\`;
                }).join('');
            })
            .catch(() => {
                document.getElementById('log-entries').innerHTML = '<p>No log entries available</p>';
            });
    </script>
</body>
</html>
EOF

    log_success "HTML report generated: $REPORT_FILE"
}

# Generate JSON report
generate_json_report() {
    log_info "Generating JSON report..."
    
    local json_report="$REPORT_DIR/upgrade-report_$TIMESTAMP.json"
    
    cat > "$json_report" << EOF
{
    "report": {
        "timestamp": "$(date -Iseconds)",
        "version": "1.0.0",
        "type": "upgrade-report"
    },
    "summary": {
        "upgrade_status": "$(cat "$METRICS_FILE" | jq -r '.upgrade.status // "unknown"')",
        "duration_seconds": $(cat "$METRICS_FILE" | jq -r '.upgrade.duration_seconds // 0'),
        "test_results": $(cat "$TEST_REPORT" 2>/dev/null || echo '{"summary": {"total_tests": 0, "passed": 0, "failed": 0, "skipped": 0}}'),
        "system_info": $(cat "$SYSTEM_INFO" 2>/dev/null || echo '{"os": {"name": "unknown"}}'),
        "metrics": $(cat "$METRICS_FILE" 2>/dev/null || echo '{"upgrade": {"duration_seconds": 0}}')
    },
    "recommendations": [
        "Monitor system resources for the next 24 hours",
        "Review application logs for any anomalies",
        "Verify backup integrity and retention policies",
        "Consider implementing automated health checks",
        "Schedule regular maintenance windows for future upgrades"
    ],
    "files": {
        "html_report": "$REPORT_FILE",
        "json_report": "$json_report",
        "system_info": "$SYSTEM_INFO",
        "test_report": "$TEST_REPORT",
        "metrics": "$METRICS_FILE",
        "upgrade_log": "$UPGRADE_LOG"
    }
}
EOF

    log_success "JSON report generated: $json_report"
}

# Generate markdown report
generate_markdown_report() {
    log_info "Generating markdown report..."
    
    local md_report="$REPORT_DIR/upgrade-report_$TIMESTAMP.md"
    
    cat > "$md_report" << EOF
# Memoria AI Upgrade Report

**Generated:** $(date '+%B %d, %Y at %I:%M %p')

## Executive Summary

### Upgrade Status
- **Status:** $(cat "$METRICS_FILE" | jq -r '.upgrade.status // "Unknown"')
- **Duration:** $(cat "$METRICS_FILE" | jq -r '.upgrade.duration_seconds // 0') seconds
- **Start Time:** $(cat "$METRICS_FILE" | jq -r '.upgrade.start_time // "Unknown"')
- **End Time:** $(cat "$METRICS_FILE" | jq -r '.upgrade.end_time // "Unknown"')

### Test Results
- **Total Tests:** $(cat "$TEST_REPORT" | jq -r '.summary.total_tests // 0')
- **Passed:** $(cat "$TEST_REPORT" | jq -r '.summary.passed // 0')
- **Failed:** $(cat "$TEST_REPORT" | jq -r '.summary.failed // 0')
- **Skipped:** $(cat "$TEST_REPORT" | jq -r '.summary.skipped // 0')
- **Pass Rate:** $(cat "$TEST_REPORT" | jq -r '.summary.pass_rate // 0')%

## System Information

- **Hostname:** $(cat "$SYSTEM_INFO" | jq -r '.hostname // "Unknown"')
- **Operating System:** $(cat "$SYSTEM_INFO" | jq -r '.os.name // "Unknown"') $(cat "$SYSTEM_INFO" | jq -r '.os.kernel // "Unknown"')
- **Architecture:** $(cat "$SYSTEM_INFO" | jq -r '.os.architecture // "Unknown"')
- **Docker Version:** $(cat "$SYSTEM_INFO" | jq -r '.docker.version // "Unknown"')
- **CPU Cores:** $(cat "$SYSTEM_INFO" | jq -r '.system.cpu_cores // "Unknown"')
- **Memory:** $(cat "$SYSTEM_INFO" | jq -r '.system.memory_gb // "Unknown"') GB
- **Disk Usage:** $(cat "$SYSTEM_INFO" | jq -r '.system.disk_usage // "Unknown"')

## Service Status

| Service | Status |
|---------|--------|
| API | $(cat "$METRICS_FILE" | jq -r '.services.api // "Unknown"') |
| PostgreSQL | $(cat "$METRICS_FILE" | jq -r '.services.postgres // "Unknown"') |
| Redis | $(cat "$METRICS_FILE" | jq -r '.services.redis // "Unknown"') |
| Weaviate | $(cat "$METRICS_FILE" | jq -r '.services.weaviate // "Unknown"') |

## Backup Information

- **Size:** $(cat "$METRICS_FILE" | jq -r '.backup.size // "0"')
- **Location:** $(cat "$METRICS_FILE" | jq -r '.backup.location // "./backups/pre-upgrade"')
- **Created:** $(cat "$METRICS_FILE" | jq -r '.backup.created // "Unknown"')

## Log Analysis

- **Log Size:** $(cat "$METRICS_FILE" | jq -r '.logs.size // "0"')
- **Errors:** $(cat "$METRICS_FILE" | jq -r '.logs.errors // 0')
- **Warnings:** $(cat "$METRICS_FILE" | jq -r '.logs.warnings // 0')

## Recent Log Entries

\`\`\`
$(tail -20 "$UPGRADE_LOG" 2>/dev/null || echo "No log entries available")
\`\`\`

## Recommendations

1. **Monitor system resources** for the next 24 hours
2. **Review application logs** for any anomalies
3. **Verify backup integrity** and retention policies
4. **Consider implementing automated health checks**
5. **Schedule regular maintenance windows** for future upgrades

## Files Generated

- HTML Report: \`$REPORT_FILE\`
- JSON Report: \`$REPORT_DIR/upgrade-report_$TIMESTAMP.json\`
- Markdown Report: \`$md_report\`
- System Info: \`$SYSTEM_INFO\`
- Test Report: \`$TEST_REPORT\`
- Metrics: \`$METRICS_FILE\`
- Upgrade Log: \`$UPGRADE_LOG\`
EOF

    log_success "Markdown report generated: $md_report"
}

# Generate all reports
generate_all_reports() {
    collect_system_info
    collect_upgrade_metrics
    
    generate_html_report
    generate_json_report
    generate_markdown_report
    
    log_success "All reports generated successfully!"
    log_info "Reports available in: $REPORT_DIR"
}

# Main function
main() {
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                 Memoria AI Upgrade Report                    ║"
    echo "║              Comprehensive Upgrade Analysis                  ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # Create report directory
    create_report_dir
    
    case "${1:-}" in
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --help, -h         Show this help message"
            echo "  --html             Generate HTML report only"
            echo "  --json             Generate JSON report only"
            echo "  --markdown         Generate Markdown report only"
            echo "  --all              Generate all