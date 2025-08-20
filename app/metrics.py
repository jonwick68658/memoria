from prometheus_client import Counter, Histogram, Gauge, generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
from functools import wraps
import time
import logging
from typing import Dict, Any
import json

logger = logging.getLogger(__name__)

# Create a registry
REGISTRY = CollectorRegistry()

# Memory processing metrics
memory_processed_total = Counter(
    'memoria_memories_processed_total',
    'Total memories processed',
    ['user_id', 'status'],
    registry=REGISTRY
)

memory_processing_duration = Histogram(
    'memoria_memory_processing_seconds',
    'Time spent processing memories',
    ['user_id', 'task_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    registry=REGISTRY
)

active_memory_tasks = Gauge(
    'memoria_active_memory_tasks',
    'Number of active memory processing tasks',
    ['user_id'],
    registry=REGISTRY
)

memory_processing_errors = Counter(
    'memoria_memory_processing_errors_total',
    'Total memory processing errors',
    ['user_id', 'error_type'],
    registry=REGISTRY
)

# API metrics
api_requests_total = Counter(
    'memoria_api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status_code'],
    registry=REGISTRY
)

api_request_duration = Histogram(
    'memoria_api_request_seconds',
    'API request duration',
    ['endpoint', 'method'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
    registry=REGISTRY
)

# System metrics
system_memory_usage = Gauge(
    'memoria_system_memory_usage_bytes',
    'System memory usage in bytes',
    registry=REGISTRY
)

system_cpu_usage = Gauge(
    'memoria_system_cpu_usage_percent',
    'System CPU usage percentage',
    registry=REGISTRY
)

# Task queue metrics
celery_tasks_total = Counter(
    'memoria_celery_tasks_total',
    'Total Celery tasks',
    ['task_name', 'state'],
    registry=REGISTRY
)

celery_task_duration = Histogram(
    'memoria_celery_task_seconds',
    'Celery task duration',
    ['task_name'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    registry=REGISTRY
)

queue_length = Gauge(
    'memoria_queue_length',
    'Length of task queue',
    ['queue_name'],
    registry=REGISTRY
)

class MetricsCollector:
    """Centralized metrics collection"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def record_memory_processing(self, user_id: str, task_type: str, duration: float, status: str = "success", error_type: str = None):
        """Record memory processing metrics"""
        memory_processed_total.labels(user_id=user_id, status=status).inc()
        memory_processing_duration.labels(user_id=user_id, task_type=task_type).observe(duration)
        
        if status == "error" and error_type:
            memory_processing_errors.labels(user_id=user_id, error_type=error_type).inc()
    
    def record_api_request(self, endpoint: str, method: str, duration: float, status_code: int):
        """Record API request metrics"""
        api_requests_total.labels(endpoint=endpoint, method=method, status_code=str(status_code)).inc()
        api_request_duration.labels(endpoint=endpoint, method=method).observe(duration)
    
    def update_active_tasks(self, user_id: str, count: int):
        """Update active task count"""
        active_memory_tasks.labels(user_id=user_id).set(count)
    
    def record_celery_task(self, task_name: str, duration: float, state: str = "success"):
        """Record Celery task metrics"""
        celery_tasks_total.labels(task_name=task_name, state=state).inc()
        celery_task_duration.labels(task_name=task_name).observe(duration)
    
    def update_queue_length(self, queue_name: str, length: int):
        """Update queue length metric"""
        queue_length.labels(queue_name=queue_name).set(length)

# Global metrics collector instance
metrics = MetricsCollector()

def track_memory_processing(task_type: str):
    """Decorator to track memory processing tasks"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            user_id = kwargs.get('user_id', 'unknown')
            
            try:
                active_memory_tasks.labels(user_id=user_id).inc()
                result = func(*args, **kwargs)
                
                duration = time.time() - start_time
                metrics.record_memory_processing(
                    user_id=user_id,
                    task_type=task_type,
                    duration=duration,
                    status="success"
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                error_type = type(e).__name__
                
                metrics.record_memory_processing(
                    user_id=user_id,
                    task_type=task_type,
                    duration=duration,
                    status="error",
                    error_type=error_type
                )
                
                raise
            finally:
                active_memory_tasks.labels(user_id=user_id).dec()
        
        return wrapper
    return decorator

def track_api_request(endpoint: str, method: str):
    """Decorator to track API requests"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                status_code = 200
                
                if hasattr(result, 'status_code'):
                    status_code = result.status_code
                elif isinstance(result, dict) and 'status' in result:
                    status_code = result.get('status', 200)
                
                duration = time.time() - start_time
                metrics.record_api_request(endpoint, method, duration, status_code)
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                status_code = 500
                
                metrics.record_api_request(endpoint, method, duration, status_code)
                raise
        
        return wrapper
    return decorator

def get_metrics():
    """Get Prometheus metrics"""
    return generate_latest(REGISTRY)

def get_metrics_content_type():
    """Get metrics content type"""
    return CONTENT_TYPE_LATEST

# System metrics collection
import psutil

def collect_system_metrics():
    """Collect system metrics"""
    try:
        # Memory usage
        memory = psutil.virtual_memory()
        system_memory_usage.set(memory.used)
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        system_cpu_usage.set(cpu_percent)
        
    except Exception as e:
        logger.error(f"Error collecting system metrics: {str(e)}")

# Celery task monitoring
class CeleryTaskMonitor:
    """Monitor Celery tasks for metrics"""
    
    @staticmethod
    def on_task_prerun(task_id, task, args, kwargs):
        """Called before task execution"""
        task_name = task.name
        user_id = kwargs.get('user_id', 'unknown')
        metrics.update_active_tasks(user_id, 1)
    
    @staticmethod
    def on_task_success(task_id, task, args, kwargs, result):
        """Called on task success"""
        task_name = task.name
        duration = getattr(task, 'duration', 0)
        metrics.record_celery_task(task_name, duration, "success")
        
        user_id = kwargs.get('user_id', 'unknown')
        metrics.update_active_tasks(user_id, -1)
    
    @staticmethod
    def on_task_failure(task_id, task, args, kwargs, exception):
        """Called on task failure"""
        task_name = task.name
        duration = getattr(task, 'duration', 0)
        metrics.record_celery_task(task_name, duration, "failure")
        
        user_id = kwargs.get('user_id', 'unknown')
        metrics.update_active_tasks(user_id, -1)

# Queue monitoring
class QueueMonitor:
    """Monitor task queues"""
    
    def __init__(self, celery_app):
        self.celery_app = celery_app
    
    def update_queue_metrics(self):
        """Update queue length metrics"""
        try:
            with self.celery_app.connection() as connection:
                queues = ['celery', 'memory', 'summary', 'insights']
                
                for queue_name in queues:
                    try:
                        queue = self.celery_app.amqp.queues[queue_name]
                        length = queue.size(connection)
                        metrics.update_queue_length(queue_name, length)
                    except:
                        metrics.update_queue_length(queue_name, 0)
                        
        except Exception as e:
            logger.error(f"Error updating queue metrics: {str(e)}")