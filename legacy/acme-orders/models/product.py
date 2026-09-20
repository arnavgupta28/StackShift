class Product(object):
    def __init__(self, sku, name, price, quantity=None, discontinued=False):
        self.sku = sku
        self.name = name
        self.price = price
        self.quantity = quantity
        self.discontinued = discontinued
