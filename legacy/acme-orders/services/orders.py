"""Order orchestration."""

from services import pricing, inventory, notifications
from repositories import order_repo
from models.order import Order
import config


def create_order(customer, items, coupon=None):
    total = pricing.calculate_total(customer, items, coupon)

    for item in items:
        if not inventory.check_available(item["sku"], item["quantity"]):
            raise ValueError("insufficient stock for %s" % item["sku"])

    order = Order(customer_id=customer.id, total=total, status="pending")
    order_id = order_repo.insert(order, items)

    inventory.reserve_stock(order_id, items)

    notifications.queue_confirmation(order_id)
    order_repo.write_audit(order_id, "created")

    return order_id


def cancel_order(order_id):
    order = order_repo.get(order_id)
    if order["status"] == "shipped":
        raise ValueError("cannot cancel shipped order")

    inventory.release_stock(order_id)
    order_repo.update_status(order_id, "cancelled")
    order_repo.write_audit(order_id, "cancelled")


def record_payment_failure(order_id):
    count = order_repo.increment_retry(order_id)
    if count >= config.MAX_PAYMENT_RETRIES:
        order_repo.update_status(order_id, "payment_disabled")
        notifications.queue_payment_disabled(order_id)
    return count
