from celery import Celery
from celery.schedules import crontab
import os

celery_app = Celery(
    'placement_portal',
    broker='redis://localhost:6379/1',
    backend='redis://localhost:6379/2',
    include=['tasks.jobs']
)

# Development vs Production mode
CELERY_EAGER = os.getenv('CELERY_ALWAYS_EAGER', 'False').lower() == 'true'

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Kolkata',
    enable_utc=True,
    worker_pool='solo',  # Use solo pool on Windows to avoid multiprocessing issues
    task_always_eager=CELERY_EAGER,  # Set to False in production to queue tasks to Redis
    task_acks_late=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        'daily-deadline-reminders': {
            'task': 'tasks.jobs.send_daily_deadline_reminders',
            'schedule': crontab(hour=9, minute=0),
        },
        'monthly-activity-report': {
            'task': 'tasks.jobs.send_monthly_activity_report',
            'schedule': crontab(day_of_month=1, hour=8, minute=0),
        },
    }
)
