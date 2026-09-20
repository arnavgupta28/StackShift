# acme-orders

Order management service.

## Running

    pip install -r requirements.txt
    mysql -u root acme_orders < schema.sql
    python app.py

Celery workers:

    celery -A workers.tasks worker

## Notes

TODO: document the pricing rules (ask Priya, she wrote them)
TODO: the reorder report is wrong sometimes, not sure why
