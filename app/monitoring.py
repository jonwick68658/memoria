from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
import redis
import psutil
import time
import logging
from typing import Dict, Any, List
import json
from datetime import datetime, timedelta

from .database import get_db
from .celery_app import celery_app
from .metrics import get_metrics, get_metrics_content_type, collect_system_metrics, metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

class HealthChecker:
    """Comprehensive health checking for the async system"""
    
    def __init__(self):
        self.checks = {}
        self.last_check = None
        self.cache_duration = 5  # seconds
    
    def check_database(self, db: Session) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = time.time()
            db.execute(text("SELECT 1"))
            response_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity and performance"""
        try:
            start_time = time.time()
            redis_client = redis.from_url(celery_app.conf.broker_url)
            redis_client.ping()
            response_time = time.time() - start_time
            
            # Check queue lengths
            queues = ['celery', 'memory', 'summary', 'insights']
            queue_info = {}
            
            for queue in queues:
                try:
                    length = redis_client.llen(queue)
                    queue_info[queue] = length
                except:
                    queue_info[queue] = 0
            
            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "queues": queue_info,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_celery_workers(self) -> Dict[str, Any]:
        """Check Celery worker status"""
        try:
            # Get worker statistics
            inspect = celery_app.control.inspect()
            
            # Check active workers
            active_workers = inspect.active()
            scheduled_tasks = inspect.scheduled()
            reserved_tasks = inspect.reserved()
            
            worker_count = len(active_workers) if active_workers else 0
            
            # Count total tasks
            total_active = sum(len(tasks) for tasks in active_workers.values()) if active_workers else 0
            total_scheduled = sum(len(tasks) for tasks in scheduled_tasks.values()) if scheduled_tasks else 0
            total_reserved = sum(len(tasks) for tasks in reserved_tasks.values()) if reserved_tasks else 0
            
            return {
                "status": "healthy" if worker_count > 0 else "unhealthy",
                "worker_count": worker_count,
                "total_active_tasks": total_active,
                "total_scheduled_tasks": total_scheduled,
                "total_reserved_tasks": total_reserved,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage = {
                "total_gb": round(memory.total / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "percent": memory.percent
            }
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage = {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": round((disk.used / disk.total) * 100, 2)
            }
            
            # Load average (Unix systems)
            try:
                load_avg = psutil.getloadavg()
                load_info = {
                    "1min": round(load_avg[0], 2),
                    "5min": round(load_avg[1], 2),
                    "15min": round(load_avg[2], 2)
                }
            except:
                load_info = None
            
            status = "healthy"
            if cpu_percent > 90 or memory.percent > 90 or disk_usage["percent"] > 90:
                status = "warning"
            if cpu_percent > 95 or memory.percent > 95 or disk_usage["percent"] > 95:
                status = "critical"
            
            return {
                "status": status,
                "cpu_percent": cpu_percent,
                "memory": memory_usage,
                "disk": disk_usage,
                "load_average": load_info,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def check_task_processing(self) -> Dict[str, Any]:
        """Check task processing health"""
        try:
            # Get task statistics from metrics
            from .metrics import REGISTRY
            
            # Collect recent task metrics
            task_stats = {
                "memory_processed_total": 0,
                "memory_processing_errors": 0,
                "active_tasks": 0
            }
            
            # This would need to be enhanced with actual task tracking
            return {
                "status": "healthy",
                "stats": task_stats,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_health_status(self, db: Session) -> Dict[str, Any]:
        """Get comprehensive health status"""
        current_time = time.time()
        
        # Check if we should use cached results
        if (self.last_check and 
            current_time - self.last_check < self.cache_duration):
            return self.checks
        
        # Perform all health checks
        checks = {
            "database": self.check_database(db),
            "redis": self.check_redis(),
            "celery_workers": self.check_celery_workers(),
            "system_resources": self.check_system_resources(),
            "task_processing": self.check_task_processing()
        }
        
        # Determine overall status
        overall_status = "healthy"
        for check_name, check_result in checks.items():
            if check_result["status"] == "unhealthy":
                overall_status = "unhealthy"
                break
            elif check_result["status"] == "warning" and overall_status == "healthy":
                overall_status = "warning"
        
        # Collect system metrics
        collect_system_metrics()
        
        health_status = {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks,
            "uptime_seconds": int(time.time() - start_time) if 'start_time' in globals() else 0
        }
        
        # Cache results
        self.checks = health_status
        self.last_check = current_time
        
        return health_status

# Global health checker instance
health_checker = HealthChecker()

# Application start time
start_time = time.time()

@router.get("/", response_model=Dict[str, Any])
async def health_check(db: Session = Depends(get_db)):
    """Comprehensive health check endpoint"""
    return health_checker.get_health_status(db)

@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Kubernetes readiness probe"""
    health = health_checker.get_health_status(db)
    
    # Only check critical services for readiness
    critical_services = ["database", "redis", "celery_workers"]
    ready = all(
        health["checks"].get(service, {}).get("status") == "healthy"
        for service in critical_services
    )
    
    if ready:
        return {"status": "ready", "timestamp": datetime.utcnow().isoformat()}
    else:
        raise HTTPException(status_code=503, detail="Service not ready")

@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe"""
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}

@router.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(
        content=get_metrics(),
        media_type=get_metrics_content_type()
    )

@router.get("/status")
async def detailed_status(db: Session = Depends(get_db)):
    """Detailed system status with recommendations"""
    health = health_checker.get_health_status(db)
    
    # Add recommendations based on health status
    recommendations = []
    
    if health["checks"]["system_resources"]["status"] == "warning":
        recommendations.append("Consider scaling up resources")
    
    if health["checks"]["celery_workers"]["worker_count"] < 2:
        recommendations.append("Consider adding more Celery workers")
    
    if health["checks"]["redis"]["status"] != "healthy":
        recommendations.append("Check Redis connection and configuration")
    
    # Task queue analysis
    redis_info = health["checks"]["redis"]
    if "queues" in redis_info:
        long_queues = [
            queue for queue, length in redis_info["queues"].items()
            if length > 100
        ]
        if long_queues:
            recommendations.append(f"Long queues detected: {', '.join(long_queues)}")
    
    return {
        "health": health,
        "recommendations": recommendations,
        "timestamp": datetime.utcnow().isoformat()
    }

class TaskMonitor:
    """Monitor task processing and provide insights"""
    
    @staticmethod
    def get_task_statistics() -> Dict[str, Any]:
        """Get detailed task statistics"""
        try:
            inspect = celery_app.control.inspect()
            
            # Get all task information
            active = inspect.active() or {}
            scheduled = inspect.scheduled() or {}
            reserved = inspect.reserved() or {}
            stats = inspect.stats() or {}
            
            # Process task information
            task_summary = {
                "total_active_tasks": sum(len(tasks) for tasks in active.values()),
                "total_scheduled_tasks": sum(len(tasks) for tasks in scheduled.values()),
                "total_reserved_tasks": sum(len(tasks) for tasks in reserved.values()),
                "worker_count": len(active),
                "workers": {}
            }
            
            # Detailed worker information
            for worker_name, tasks in active.items():
                task_summary["workers"][worker_name] = {
                    "active_tasks": len(tasks),
                    "scheduled_tasks": len(scheduled.get(worker_name, [])),
                    "reserved_tasks": len(reserved.get(worker_name, [])),
                    "stats": stats.get(worker_name, {})
                }
            
            return task_summary
            
        except Exception as e:
            return {"error": str(e)}

@router.get("/tasks")
async def task_statistics():
    """Get detailed task processing statistics"""
    return TaskMonitor.get_task_statistics()

@router.get("/performance")
async def performance_metrics():
    """Get performance metrics and trends"""
    # This would integrate with your metrics system
    # For now, return basic performance info
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": {
            "api_response_time_ms": "collected_via_prometheus",
            "task_processing_time_ms": "collected_via_prometheus",
            "memory_usage_mb": "collected_via_prometheus",
            "error_rate": "collected_via_prometheus"
        },
        "prometheus_endpoint": "/health/metrics"
    }