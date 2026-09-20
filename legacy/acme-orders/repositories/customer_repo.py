import MySQLdb
import config
from models.customer import Customer

_conn = None


def _cursor():
    global _conn
    if _conn is None:
        _conn = MySQLdb.connect(
            host=config.DB_HOST, user=config.DB_USER,
            passwd=config.DB_PASS, db=config.DB_NAME,
        )
    return _conn.cursor()


def get(customer_id):
    cur = _cursor()
    cur.execute("SELECT id, email, vip, region FROM customers WHERE id = %s",
                (customer_id,))
    row = cur.fetchone()
    return Customer(id=row[0], email=row[1], vip=bool(row[2]), region=row[3])
