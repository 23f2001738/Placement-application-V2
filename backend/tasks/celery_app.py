from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    'placement_portal',
    broker='redis://localhost:6379/1',
    backend='redis://localhost:6379/2',
    include=['tasks.jobs']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Kolkata',
    enable_utc=True,
    worker_pool='solo',  # Use solo pool on Windows to avoid multiprocessing issues
    task_always_eager=True,  # Execute tasks synchronously during development
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
