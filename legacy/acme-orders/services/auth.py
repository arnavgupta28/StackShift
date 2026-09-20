"""Session handling. Tokens are opaque strings in Redis."""

import redis
import config

_r = redis.Redis.from_url(config.CELERY_BROKER)


def require_user(request):
    token = request.headers.get("X-Auth-Token")
    if not token:
        raise PermissionError("missing token")
    raw = _r.get("session:%s" % token)
    if raw is None:
        raise PermissionError("invalid token")
    customer_id, role = raw.decode().split(":")
    return {"customer_id": int(customer_id), "role": role}


def require_admin(request):
    user = require_user(request)
    if user["role"] != "admin":
        raise PermissionError("admin required")
    return user
