"""Stock tracking."""

from repositories import order_repo


def check_available(sku, quantity):
    stock = order_repo.get_stock(sku)
    if stock is None:
        return False
    return stock >= quantity


def reserve_stock(order_id, items):
    for item in items:
        order_repo.decrement_stock(item["sku"], item["quantity"])
    order_repo.write_audit(order_id, "stock_reserved")


def release_stock(order_id):
    items = order_repo.get_items(order_id)
    for item in items:
        order_repo.increment_stock(item["sku"], item["quantity"])


def needs_reorder():
    """Items that have fallen below the reorder threshold."""
    return order_repo.find_lowest_stock_items()
