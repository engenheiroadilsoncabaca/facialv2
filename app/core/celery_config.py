from celery import Celery
import os

celery_app = Celery(
    'hunter_app',
    broker='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0'
)
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=True,
    task_track_started=True
)