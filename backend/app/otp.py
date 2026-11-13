"""Server-side phone OTP storage, rate limiting and verification (Redis cache).

The code itself never leaves the server except by SMS. Only an HMAC of it is
cached, keyed by phone number, and it expires after OTP_TTL_SECONDS.
"""
import re
import secrets

from django.conf import settings
from django.core.cache import cache
from django.utils.crypto import constant_time_compare, salted_hmac

_SALT = "app.otp"


def normalize_phone(phone):
    return re.sub(r"[\s\-()]", "", str(phone or ""))


def _key(kind, ident):
    return f"otp:{kind}:{ident}"


def _digest(phone, code):
    return salted_hmac(_SALT, f"{phone}:{code}").hexdigest()


def _incr_window(key, window):
    """Increment a fixed-window counter; returns the new count."""
    if cache.add(key, 1, window):
        return 1
    try:
        return cache.incr(key)
    except ValueError:  # expired between add() and incr()
        cache.set(key, 1, window)
        return 1


def check_send_allowed(phone, client_ip):
    """Return (allowed, retry_after_seconds)."""
    if cache.get(_key("cooldown", phone)):
        return False, settings.OTP_RESEND_COOLDOWN_SECONDS
    if _incr_window(_key("sends", phone), 3600) > settings.OTP_MAX_SENDS_PER_HOUR:
        return False, 3600
    if client_ip and _incr_window(_key("ip", client_ip), 3600) > settings.OTP_MAX_SENDS_PER_IP_PER_HOUR:
        return False, 3600
    return True, 0


def issue(phone):
    """Generate, store and return a new 6-digit code for ``phone``."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    cache.set(_key("code", phone), _digest(phone, code), settings.OTP_TTL_SECONDS)
    cache.delete(_key("attempts", phone))
    cache.set(_key("cooldown", phone), 1, settings.OTP_RESEND_COOLDOWN_SECONDS)
    return code


def discard(phone):
    """Forget a code that could not be delivered (and lift the cooldown)."""
    cache.delete_many([_key("code", phone), _key("cooldown", phone)])


def verify(phone, code):
    """Return "ok", "invalid", "expired" or "locked"."""
    stored = cache.get(_key("code", phone))
    if not stored:
        return "expired"
    if _incr_window(_key("attempts", phone), settings.OTP_TTL_SECONDS) > settings.OTP_MAX_VERIFY_ATTEMPTS:
        cache.delete(_key("code", phone))
        return "locked"
    if constant_time_compare(stored, _digest(phone, str(code or "").strip())):
        cache.delete_many([_key("code", phone), _key("attempts", phone)])
        return "ok"
    return "invalid"
