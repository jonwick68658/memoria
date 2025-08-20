#!/usr/bin/env python3
"""
Complete startup script for Memoria async system
Starts all services in the correct order with proper configuration
"""

import os
import sys
import subprocess
import time
import signal
import logging
from pathlib import Path
import json
import platform
import threading
import queue
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ServiceManager:
    """Manages all services for the async system"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.processes = []
        self.running = False
        self.setup_logging()
        
    def setup_logging(self):
        """Setup logging for the service manager"""
        log_dir = self.project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # File handler for service manager logs
        file_handler = logging.FileHandler(log_dir / "service_manager.log")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        
        logger.addHandler(file_handler)
    
    def check_service_health(self, url: str, timeout: int = 30) -> bool:
        """Check if a service is healthy"""
        import requests
        
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def start_redis(self) -> subprocess.Popen:
        """Start Redis server"""
        logger.info("Starting Redis...")
        
        # Check if Redis is already running
        if self.check_service_health("http://localhost:6379"):
            logger.info("Redis is already running")
            return None
        
        # Try to start Redis
        try:
            if platform.system() == "Windows":
                # Windows Redis startup
                redis_process = subprocess.Popen(
                    ["redis-server", "--port", "6379"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            else:
                # Unix-like systems
                redis_process = subprocess.Popen(
                    ["redis-server", "--port", "6379", "--daemonize", "no"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            
            # Wait for Redis to start
            time.sleep(3)
            
            if redis_process.poll() is None:
                logger.info("Redis started successfully")
                return redis_process
            else:
                logger.error("Failed to start Redis")
                return None
                
        except FileNotFoundError:
            logger.error("Redis not found. Please install Redis first.")
            return None
    
    def start_postgresql(self) -> subprocess.Popen:
        """Start PostgreSQL (if using local setup)"""
        logger.info("Checking PostgreSQL...")
        
        # Check if PostgreSQL is running
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="memoria",
                user="memoria",
                password="memoria"
            )
            conn.close()
            logger.info("PostgreSQL is running")
            return None
        except:
            logger.warning("PostgreSQL not accessible - using Docker setup")
            return None
    
    def start_celery_worker(self) -> subprocess.Popen:
        """Start Celery worker"""
        logger.info("Starting Celery worker...")
        
        # Set environment variables
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.project_root)
        
        worker_process = subprocess.Popen([
            sys.executable, "-m", "celery",
            "-A", "app.celery_app",
            "worker",
            "--loglevel=info",
            "--concurrency=4",
            "--pool=prefork",
            "--hostname=worker@%h"
        ], env=env, cwd=str(self.project_root))
        
        logger.info("Celery worker started")
        return worker_process
    
    def start_celery_beat(self) -> subprocess.Popen:
        """Start Celery beat scheduler"""
        logger.info("Starting Celery beat...")
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.project_root)
        
        beat_process = subprocess.Popen([
            sys.executable, "-m", "celery",
            "-A", "app.celery_app",
            "beat",
            "--loglevel=info",
            "--schedule=celerybeat-schedule"
        ], env=env, cwd=str(self.project_root))
        
        logger.info("Celery beat started")
        return beat_process
    
    def start_fastapi(self) -> subprocess.Popen:
        """Start FastAPI server"""
        logger.info("Starting FastAPI server...")
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.project_root)
        
        api_process = subprocess.Popen([
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ], env=env, cwd=str(self.project_root))
        
        logger.info("FastAPI server started")
        return api_process
    
    def start_flower(self) -> subprocess.Popen:
        """Start Flower monitoring"""
        logger.info("Starting Flower monitoring...")
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.project_root)
        
        flower_process = subprocess.Popen([
            sys.executable, "-m", "celery",
            "-A", "app.celery_app",
            "flower",
            "--port=5555",
            "--address=0.0.0.0",
            "--basic_auth=admin:admin"
        ], env=env, cwd=str(self.project_root))
        
        logger.info("Flower monitoring started")
        return flower_process
    
    def start_docker_services(self):
        """Start services using Docker Compose"""
        logger.info("Starting services with Docker Compose...")
        
        try:
            # Check if Docker Compose is available
            subprocess.run(["docker-compose", "--version"], check=True, capture_output=True)
            
            # Start services
            subprocess.run([
                "docker-compose", "up", "-d"
            ], check=True, cwd=str(self.project_root))
            
            logger.info("Docker services started")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker Compose failed: {e}")
            return False
        except FileNotFoundError:
            logger.error("Docker Compose not found")
            return False
    
    def wait_for_services(self, services: List[str], timeout: int = 60):
        """Wait for services to become available"""
        logger.info("Waiting for services to start...")
        
        service_urls = {
            "redis": "http://localhost:6379",
            "api": "http://localhost:8000/health",
            "flower": "http://localhost:5555",
            "database": "http://localhost:8000/health"
        }
        
        start_time = time.time()
        
        for service in services:
            if service not in service_urls:
                continue
                
            url = service_urls[service]
            logger.info(f"Waiting for {service}...")
            
            while time.time() - start_time < timeout:
                if self.check_service_health(url):
                    logger.info(f"{service} is ready ✓")
                    break
                time.sleep(2)
            else:
                logger.warning(f"{service} not ready after {timeout}s")
    
    def create_service_config(self):
        """Create service configuration"""
        config = {
            "services": {
                "redis": {
                    "host": "localhost",
                    "port": 6379,
                    "enabled": True
                },
                "api": {
                    "host": "localhost",
                    "port": 8000,
                    "enabled": True
                },
                "flower": {
                    "host": "localhost",
                    "port": 5555,
                    "enabled": True
                },
                "celery": {
                    "worker_count": 4,
                    "queues": ["celery", "memory", "summary", "insights"]
                }
            },
            "monitoring": {
                "health_check_interval": 30,
                "metrics_port": 8001
            }
        }
        
        config_file = self.project_root / "config" / "services.json"
        config_file.parent.mkdir(exist_ok=True)
        config_file.write_text(json.dumps(config, indent=2))
        
        return config
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal, stopping services...")
        self.stop_all_services()
        sys.exit(0)
    
    def stop_all_services(self):
        """Stop all running services"""
        logger.info("Stopping all services...")
        
        for process in self.processes:
            if process and process.poll() is None:
                logger.info(f"Stopping process {process.pid}")
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing process {process.pid}")
                    process.kill()
        
        # Stop Docker services if running
        try:
            subprocess.run([
                "docker-compose", "down"
            ], cwd=str(self.project_root), timeout=30)
            logger.info("Docker services stopped")
        except:
            pass
    
    def start_all_services(self, use_docker: bool = False):
        """Start all services"""
        logger.info("Starting Memoria async system...")
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        if use_docker:
            # Use Docker Compose
            if not self.start_docker_services():
                logger.error("Failed to start Docker services")
                return False
            
            # Wait for services
            self.wait_for_services(["redis", "api", "flower"])
            
        else:
            # Start services individually
            services = []
            
            # Start Redis
            redis_process = self.start_redis()
            if redis_process:
                services.append(("Redis", redis_process))
            
            # Start PostgreSQL (if needed)
            pg_process = self.start_postgresql()
            if pg_process:
                services.append(("PostgreSQL", pg_process))
            
            # Start Celery worker
            worker_process = self.start_celery_worker()
            services.append(("Celery Worker", worker_process))
            
            # Start Celery beat
            beat_process = self.start_celery_beat()
            services.append(("Celery Beat", beat_process))
            
            # Start FastAPI
            api_process = self.start_fastapi()
            services.append(("FastAPI", api_process))
            
            # Start Flower
            flower_process = self.start_flower()
            services.append(("Flower", flower_process))
            
            self.processes = [p for _, p in services]
            
            # Wait for services
            self.wait_for_services(["redis", "api", "flower"])
        
        # Create service configuration
        self.create_service_config()
        
        # Display startup information
        self.display_startup_info()
        
        # Keep the script running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_all_services()
    
    def display_startup_info(self):
        """Display startup information"""
        logger.info("\n" + "="*60)
        logger.info("MEMORIA ASYNC SYSTEM STARTED SUCCESSFULLY!")
        logger.info("="*60)
        logger.info("\nServices:")
        logger.info("  🚀 API Server: http://localhost:8000")
        logger.info("  📊 API Docs: http://localhost:8000/docs")
        logger.info("  🌸 Flower Dashboard: http://localhost:5555")
        logger.info("  📈 Health Check: http://localhost:8000/health")
        logger.info("  📊 Metrics: http://localhost:8000/health/metrics")
        logger.info("\nAuthentication:")
        logger.info("  Flower: admin/admin")
        logger.info("\nCommands:")
        logger.info("  Test performance: python scripts/test_async_performance.py")
        logger.info("  Stop services: Ctrl+C")
        logger.info("="*60)

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Start Memoria async system")
    parser.add_argument(
        "--docker", 
        action="store_true", 
        help="Use Docker Compose instead of local services"
    )
    parser.add_argument(
        "--no-flower", 
        action="store_true", 
        help="Don't start Flower monitoring"
    )
    
    args = parser.parse_args()
    
    manager = ServiceManager()
    manager.start_all_services(use_docker=args.docker)

if __name__ == "__main__":
    main()