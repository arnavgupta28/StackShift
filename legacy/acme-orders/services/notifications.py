"""Outbound email, queued through Celery."""

from workers.tasks import send_email


def queue_confirmation(order_id):
    send_email.delay("order_confirmation", order_id)


def queue_payment_disabled(order_id):
    send_email.delay("payment_disabled", order_id)


def queue_cancellation(order_id):
    send_email.delay("order_cancelled", order_id)
