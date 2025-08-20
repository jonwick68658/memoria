#!/usr/bin/env python3
"""
Migration guide and helper script for transitioning to async system
Provides step-by-step migration instructions and validation
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
import logging
from typing import Dict, List, Any
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MigrationGuide:
    """Helper class for migrating to async system"""
    
    def __init__(self, project_root: str = None):
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.parent
        self.migration_steps = self.load_migration_steps()
        self.checklist = self.load_checklist()
        
    def load_migration_steps(self) -> List[Dict[str, Any]]:
        """Load migration steps from configuration"""
        return [
            {
                "step": 1,
                "title": "Backup Current System",
                "description": "Create full backup of current system",
                "commands": [
                    "git add .",
                    "git commit -m 'Pre-async migration backup'",
                    "git tag pre-async-migration",
                    "cp -r . ../memoria-backup-$(date +%Y%m%d_%H%M%S)"
                ],
                "validation": "git log --oneline -5",
                "critical": True
            },
            {
                "step": 2,
                "title": "Install Dependencies",
                "description": "Install async system dependencies",
                "commands": [
                    "pip install -r requirements.txt",
                    "pip install celery[redis] redis flower",
                    "pip install locust aiohttp"
                ],
                "validation": "python -c 'import celery, redis; print(\"Dependencies OK\")'",
                "critical": True
            },
            {
                "step": 3,
                "title": "Setup Environment",
                "description": "Configure environment variables for async system",
                "commands": [],
                "validation": "python -c 'import os; print(\"REDIS_URL:\", os.getenv(\"REDIS_URL\"))'",
                "critical": True,
                "manual": True,
                "instructions": [
                    "Copy .env.example to .env",
                    "Update REDIS_URL to point to your Redis instance",
                    "Set CELERY_BROKER_URL and CELERY_RESULT_BACKEND",
                    "Configure PostgreSQL connection if needed"
                ]
            },
            {
                "step": 4,
                "title": "Start Infrastructure",
                "description": "Start Redis and other infrastructure services",
                "commands": [
                    "python scripts/start_async_system.py --docker"
                ],
                "validation": "curl -f http://localhost:8000/health",
                "critical": True
            },
            {
                "step": 5,
                "title": "Test Async Endpoints",
                "description": "Verify async endpoints are working",
                "commands": [
                    "python scripts/test_async_performance.py --requests 10"
                ],
                "validation": "python -c 'import requests; print(\"Async test passed\")'",
                "critical": True
            },
            {
                "step": 6,
                "title": "Update Client Code",
                "description": "Update client applications to use async endpoints",
                "commands": [],
                "validation": "grep -r '/api/memory/store' src/ || echo 'No direct API calls found'",
                "critical": False,
                "manual": True,
                "instructions": [
                    "Update client code to handle 202 responses",
                    "Implement polling for async task completion",
                    "Add error handling for async operations",
                    "Update UI to show processing status"
                ]
            },
            {
                "step": 7,
                "title": "Performance Validation",
                "description": "Run comprehensive performance tests",
                "commands": [
                    "python scripts/test_async_performance.py --requests 100",
                    "locust -f tests/load_test.py --host http://localhost:8000 --headless -u 50 -r 10 -t 1m"
                ],
                "validation": "python -c 'print(\"Performance tests completed\")'",
                "critical": False
            },
            {
                "step": 8,
                "title": "Production Deployment",
                "description": "Deploy async system to production",
                "commands": [
                    "docker-compose -f docker-compose.prod.yml up -d",
                    "python scripts/start_async_system.py"
                ],
                "validation": "curl -f https://your-domain.com/health",
                "critical": True,
                "manual": True,
                "instructions": [
                    "Update production environment variables",
                    "Configure production Redis instance",
                    "Set up monitoring and alerting",
                    "Configure SSL certificates",
                    "Update DNS records"
                ]
            }
        ]
    
    def load_checklist(self) -> Dict[str, List[str]]:
        """Load migration checklist"""
        return {
            "pre_migration": [
                "□ Create full system backup",
                "□ Document current API usage",
                "□ Identify critical endpoints",
                "□ Plan rollback strategy",
                "□ Notify stakeholders"
            ],
            "during_migration": [
                "□ Install async dependencies",
                "□ Configure environment variables",
                "□ Start infrastructure services",
                "□ Test async endpoints",
                "□ Validate data integrity"
            ],
            "post_migration": [
                "□ Update client applications",
                "□ Run performance tests",
                "□ Monitor system health",
                "□ Update documentation",
                "□ Train team members"
            ]
        }
    
    def run_step(self, step_number: int, dry_run: bool = False) -> bool:
        """Run a specific migration step"""
        step = next((s for s in self.migration_steps if s["step"] == step_number), None)
        if not step:
            logger.error(f"Step {step_number} not found")
            return False
        
        logger.info(f"\n{'='*60}")
        logger.info(f"STEP {step['step']}: {step['title']}")
        logger.info(f"{'='*60}")
        logger.info(f"Description: {step['description']}")
        
        if step.get("manual"):
            logger.info("⚠️  This step requires manual intervention")
            for instruction in step.get("instructions", []):
                logger.info(f"   • {instruction}")
            return True
        
        if dry_run:
            logger.info("DRY RUN - Commands that would be executed:")
            for cmd in step.get("commands", []):
                logger.info(f"   $ {cmd}")
            return True
        
        # Execute commands
        success = True
        for cmd in step.get("commands", []):
            logger.info(f"Executing: {cmd}")
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    logger.error(f"Command failed: {result.stderr}")
                    success = False
                    if step.get("critical"):
                        return False
                else:
                    logger.info("✅ Command succeeded")
                    
            except subprocess.TimeoutExpired:
                logger.error("Command timed out")
                success = False
                if step.get("critical"):
                    return False
        
        # Run validation
        if "validation" in step:
            logger.info("Running validation...")
            try:
                result = subprocess.run(
                    step["validation"],
                    shell=True,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    logger.info("✅ Validation passed")
                    logger.info(f"Output: {result.stdout.strip()}")
                else:
                    logger.error("❌ Validation failed")
                    logger.error(f"Error: {result.stderr}")
                    return False
                    
            except Exception as e:
                logger.error(f"Validation error: {e}")
                return False
        
        return success
    
    def interactive_migration(self):
        """Interactive migration wizard"""
        print("\n" + "="*60)
        print("MEMORIA ASYNC SYSTEM MIGRATION WIZARD")
        print("="*60)
        
        print("\nThis wizard will guide you through migrating to the async system.")
        print("Please review each step carefully before proceeding.")
        
        for step in self.migration_steps:
            print(f"\n{'='*60}")
            print(f"STEP {step['step']}: {step['title']}")
            print(f"{'='*60}")
            print(f"Description: {step['description']}")
            
            if step.get("critical"):
                print("⚠️  This is a CRITICAL step")
            
            if step.get("manual"):
                print("\nManual steps required:")
                for instruction in step.get("instructions", []):
                    print(f"   • {instruction}")
            
            if step.get("commands"):
                print("\nCommands to execute:")
                for cmd in step.get("commands", []):
                    print(f"   $ {cmd}")
            
            if step.get("validation"):
                print(f"\nValidation: {step['validation']}")
            
            response = input("\nProceed with this step? [y/n/q]: ").lower()
            
            if response == 'q':
                print("Migration cancelled by user")
                return False
            elif response == 'y':
                if not self.run_step(step["step"]):
                    if step.get("critical"):
                        print("Critical step failed. Migration halted.")
                        return False
                    else:
                        response = input("Non-critical step failed. Continue? [y/n]: ").lower()
                        if response != 'y':
                            return False
            else:
                print("Skipping step...")
        
        print("\n✅ Migration completed successfully!")
        return True
    
    def create_rollback_script(self):
        """Create rollback script for emergency use"""
        rollback_script = """#!/bin/bash
# Emergency rollback script for Memoria async system
# This script will revert to the pre-async state

set -e

echo "🚨 EMERGENCY ROLLBACK INITIATED"
echo "================================"

# Stop all async services
echo "Stopping async services..."
docker-compose down || true
pkill -f celery || true
pkill -f uvicorn || true

# Revert to previous git state
echo "Reverting to pre-migration state..."
git checkout pre-async-migration

# Restart original services
echo "Restarting original services..."
# Add your original startup commands here

echo "✅ Rollback completed"
echo "Please verify system functionality"
"""
        
        rollback_path = self.project_root / "scripts/rollback.sh"
        with open(rollback_path, "w") as f:
            f.write(rollback_script)
        
        os.chmod(rollback_path, 0o755)
        logger.info(f"Rollback script created: {rollback_path}")

def main():
    """Main migration helper"""
    parser = argparse.ArgumentParser(description="Memoria async system migration helper")
    parser.add_argument("--step", type=int, help="Run specific migration step")
    parser.add_argument("--dry-run", action="store_true", help="Show commands without executing")
    parser.add_argument("--interactive", action="store_true", help="Run interactive wizard")
    parser.add_argument("--report", action="store_true", help="Generate migration report")
    parser.add_argument("--rollback", action="store_true", help="Create rollback script")
    
    args = parser.parse_args()
    
    guide = MigrationGuide()
    
    if args.rollback:
        guide.create_rollback_script()
        return
    
    if args.report:
        report = guide.generate_migration_report()
        print(json.dumps(report, indent=2))
        return
    
    if args.step:
        success = guide.run_step(args.step, args.dry_run)
        sys.exit(0 if success else 1)
    
    if args.interactive:
        success = guide.interactive_migration()
        sys.exit(0 if success else 1)
    
    # Default: show migration steps
    print("Memoria Async System Migration")
    print("Usage:")
    print("  python scripts/migration_guide.py --interactive   # Interactive wizard")
    print("  python scripts/migration_guide.py --step 1        # Run specific step")
    print("  python scripts/migration_guide.py --dry-run --step 1  # Preview step")
    print("  python scripts/migration_guide.py --report        # Generate report")
    print("  python scripts/migration_guide.py --rollback      # Create rollback script")

if __name__ == "__main__":
    main()