from celery import Celery
from config import config

# NOTE: You must have a Celery broker running (e.g., Redis or RabbitMQ)
# Replace this with your actual broker URL from config.
BROKER_URL = config.celery_broker_url
BACKEND_URL = config.celery_backend_url

celery_app = Celery(
    "event_tasks",
    broker=BROKER_URL,
    backend=BACKEND_URL,
    # This ensures the tasks are loaded when the worker starts
    include=["celery_tasks.event_tasks"] 
)

# Optional: Configure timezone or other settings
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,

    # === Producer-Side (Sending Message) Retry Settings ===
    # A boolean setting that enables retries for publishing tasks.
    # This is for when the client cannot connect to the broker.
    task_publish_retry=True,

    # A dictionary to customize the retry policy.
    task_publish_retry_policy={
        'max_retries': 10,       # Maximum number of retries before giving up
        'interval_start': 0.5,   # Initial wait time in seconds
        'interval_step': 0.5,    # Amount to increase wait time by
        'interval_max': 5,       # Maximum wait time
    },
)

# celery_app.conf.broker_transport_options = {"visibility_timeout": 14400}

celery_app.conf.task_routes = {

    # default queue
    'celery_tasks.event_tasks.*': {'queue': 'default'},
  
    # You can also use wildcards for groups of tasks.
    # 'tasks.image.*': {'queue': 'image-queue'},
}
