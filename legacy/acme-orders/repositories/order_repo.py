"""Data access. Raw SQL against MySQL."""

import MySQLdb
import config

_conn = None


def _cursor():
    global _conn
    if _conn is None:
        _conn = MySQLdb.connect(
            host=config.DB_HOST, user=config.DB_USER,
            passwd=config.DB_PASS, db=config.DB_NAME,
        )
    return _conn.cursor()


def insert(order, items):
    cur = _cursor()
    cur.execute(
        "INSERT INTO orders (customer_id, total, status) VALUES (%s, %s, %s)",
        (order.customer_id, str(order.total), order.status),
    )
    order_id = cur.lastrowid
    for item in items:
        cur.execute(
            "INSERT INTO order_items (order_id, sku, quantity, price) "
            "VALUES (%s, %s, %s, %s)",
            (order_id, item["sku"], item["quantity"], str(item["price"])),
        )
    _conn.commit()
    return order_id


def get(order_id):
    cur = _cursor()
    cur.execute("SELECT id, customer_id, total, status FROM orders WHERE id = %s",
                (order_id,))
    row = cur.fetchone()
    return {"id": row[0], "customer_id": row[1], "total": row[2], "status": row[3]}


def get_items(order_id):
    cur = _cursor()
    cur.execute("SELECT sku, quantity, price FROM order_items WHERE order_id = %s",
                (order_id,))
    return [{"sku": r[0], "quantity": r[1], "price": r[2]} for r in cur.fetchall()]


def find_lowest_stock_items():
    """Products most in need of reorder, lowest stock first.

    Discontinued products carry a NULL quantity and MUST appear at the top of
    this report so ops can clear them out of the catalogue.
    """
    cur = _cursor()
    cur.execute(
        "SELECT sku, name, quantity FROM products "
        "WHERE discontinued = 0 OR quantity IS NULL "
        "ORDER BY quantity ASC "
        "LIMIT 20"
    )
    return [{"sku": r[0], "name": r[1], "quantity": r[2]} for r in cur.fetchall()]


def get_stock(sku):
    cur = _cursor()
    cur.execute("SELECT quantity FROM products WHERE sku = %s", (sku,))
    row = cur.fetchone()
    return row[0] if row else None


def decrement_stock(sku, quantity):
    cur = _cursor()
    cur.execute("UPDATE products SET quantity = quantity - %s WHERE sku = %s",
                (quantity, sku))
    _conn.commit()


def increment_stock(sku, quantity):
    cur = _cursor()
    cur.execute("UPDATE products SET quantity = quantity + %s WHERE sku = %s",
                (quantity, sku))
    _conn.commit()


def increment_retry(order_id):
    cur = _cursor()
    cur.execute("UPDATE orders SET retry_count = retry_count + 1 WHERE id = %s",
                (order_id,))
    _conn.commit()
    cur.execute("SELECT retry_count FROM orders WHERE id = %s", (order_id,))
    return cur.fetchone()[0]


def update_status(order_id, status):
    cur = _cursor()
    cur.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
    _conn.commit()


def write_audit(order_id, action):
    cur = _cursor()
    cur.execute("INSERT INTO audit_log (order_id, action) VALUES (%s, %s)",
                (order_id, action))
    _conn.commit()
