class Customer(object):
    def __init__(self, id, email, vip=False, region="W"):
        self.id = id
        self.email = email
        self.vip = vip
        self.region = region
