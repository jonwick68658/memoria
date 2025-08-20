from celery import Celery
import os

def make_celery(app_name=__name__):
    """Create and configure Celery application"""
    celery = Celery(
        app_name,
        broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
        backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
        include=['app.tasks']
    )
    
    celery.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        task_track_started=True,
        task_time_limit=30 * 60,  # 30 minutes
        task_soft_time_limit=25 * 60,
        worker_prefetch_multiplier=1,
        worker_max_tasks_per_child=1000,
        result_expires=3600,  # 1 hour
        task_annotations={
            'app.tasks.process_memory_async': {'rate_limit': '100/m'},
            'app.tasks.batch_process_embeddings': {'rate_limit': '50/m'}
        }
    )
    
    return celery

celery = make_celery()