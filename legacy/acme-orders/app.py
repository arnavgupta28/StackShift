"""acme-orders HTTP API (Flask)."""

from flask import Flask, request, jsonify, render_template
from services import orders, auth, inventory
from repositories import customer_repo

app = Flask(__name__)


@app.route("/orders", methods=["POST"])
def create_order():
    user = auth.require_user(request)
    body = request.get_json()
    customer = customer_repo.get(user["customer_id"])
    try:
        order_id = orders.create_order(
            customer, body["items"], body.get("coupon")
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"order_id": order_id}), 201


@app.route("/orders/<int:order_id>", methods=["GET"])
def get_order(order_id):
    auth.require_user(request)
    from repositories import order_repo
    return jsonify(order_repo.get(order_id))


@app.route("/orders/<int:order_id>/cancel", methods=["POST"])
def cancel_order(order_id):
    auth.require_user(request)
    try:
        orders.cancel_order(order_id)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"status": "cancelled"})


@app.route("/orders/<int:order_id>/payment-failed", methods=["POST"])
def payment_failed(order_id):
    auth.require_user(request)
    count = orders.record_payment_failure(order_id)
    return jsonify({"retry_count": count})


@app.route("/orders/<int:order_id>/confirmation", methods=["GET"])
def confirmation(order_id):
    from repositories import order_repo
    return render_template("order_confirmation.html",
                           order=order_repo.get(order_id))


@app.route("/reports/reorder", methods=["GET"])
def reorder_report():
    auth.require_admin(request)
    return jsonify(inventory.needs_reorder())


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
