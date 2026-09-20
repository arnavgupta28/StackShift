class Order(object):
    def __init__(self, customer_id, total, status="pending", id=None):
        self.id = id
        self.customer_id = customer_id
        self.total = total
        self.status = status

    def is_cancellable(self):
        return self.status not in ("shipped", "cancelled")
