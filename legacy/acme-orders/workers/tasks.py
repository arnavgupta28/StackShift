"""Celery background jobs."""

from celery import Celery
import config

celery_app = Celery("acme", broker=config.CELERY_BROKER)


@celery_app.task(bind=True, max_retries=3)
def send_email(self, template, order_id):
    from repositories import order_repo
    order = order_repo.get(order_id)
    print("sending %s for order %s" % (template, order["id"]))


@celery_app.task
def nightly_reorder_report():
    from services import inventory
    items = inventory.needs_reorder()
    print("reorder candidates: %d" % len(items))
