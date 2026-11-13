"""Liveness/readiness endpoint used by the Docker health check."""
from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def healthz(request):
    checks, healthy = {}, True

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - reported, not raised
        checks["database"] = f"error: {exc.__class__.__name__}"
        healthy = False

    if settings.REDIS_URL:
        try:
            cache.set("healthz", "ok", 10)
            checks["redis"] = "ok" if cache.get("healthz") == "ok" else "error: read-back failed"
        except Exception as exc:
            checks["redis"] = f"error: {exc.__class__.__name__}"
        healthy = healthy and checks["redis"] == "ok"
    else:
        checks["redis"] = "not configured"
        if "DatabaseCache" in settings.CACHES["default"]["BACKEND"]:
            try:
                cache.set("healthz", "ok", 10)
                checks["cache"] = "database" if cache.get("healthz") == "ok" else "error"
            except Exception as exc:
                checks["cache"] = f"error: {exc.__class__.__name__}"
            healthy = healthy and checks["cache"] == "database"

    return JsonResponse(
        {"status": "ok" if healthy else "error", "checks": checks},
        status=200 if healthy else 503,
    )


class HealthCheckMiddleware:
    """Answer /healthz/ before host validation and SSL redirects.

    Platform health checkers (Render, Docker) may call the container with a
    Host header that is not in ALLOWED_HOSTS. Must be first in MIDDLEWARE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info == "/healthz/":
            return healthz(request)
        return self.get_response(request)
