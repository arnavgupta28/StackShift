import os

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "")
DB_NAME = os.environ.get("DB_NAME", "acme_orders")

CELERY_BROKER = os.environ.get("CELERY_BROKER", "redis://localhost:6379/0")

REORDER_THRESHOLD = 10
MAX_PAYMENT_RETRIES = 3
