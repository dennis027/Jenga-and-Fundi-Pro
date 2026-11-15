"""SMS alerts at key moments (Africa's Talking). Off unless SMS_NOTIFICATIONS=True.

Sent in the background so requests never wait on the SMS gateway. Each message
costs money, so only a few high-value events trigger one.
"""
import logging

from django.conf import settings

from .mail import _executor  # shared background thread pool

logger = logging.getLogger(__name__)

# Showcase / demo accounts (seed_showcase) use this email domain and never get texts.
DEMO_EMAIL_DOMAIN = "@demo.fundijenga.test"


def _to_e164(phone):
    p = "".join(ch for ch in str(phone or "") if ch.isdigit() or ch == "+")
    if p.startswith("+"):
        return p
    if p.startswith("254"):
        return "+" + p
    if p.startswith("0") and len(p) == 10:
        return "+254" + p[1:]
    return None


def _gateway():
    import africastalking  # initialised in settings with AT_USERNAME / AT_API_KEY
    return africastalking.SMS


def _send(to, text):
    try:
        _gateway().send(text, [to])
    except Exception:
        logger.exception("SMS alert failed")


def sms(user, text):
    """Queue an SMS to a user if alerts are enabled and they have a valid phone. Returns True if queued."""
    if not settings.SMS_NOTIFICATIONS or not user:
        return False
    if (getattr(user, "email", "") or "").endswith(DEMO_EMAIL_DOMAIN):
        return False
    to = _to_e164(getattr(user, "phone", None))
    if not to:
        return False
    text = f"{settings.SMS_SENDER_LABEL}: {text}"[:160]
    if settings.EMAIL_ASYNC:
        _executor.submit(_send, to, text)
    else:
        _send(to, text)
    return True
