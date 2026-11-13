"""Send email without blocking the request (SMTP can take seconds or time out)."""
import logging
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mail")


def _send(args, kwargs):
    try:
        send_mail(*args, **kwargs)
    except Exception:
        logger.exception("Background email failed (subject=%r)", args[0] if args else kwargs.get("subject"))


def send_mail_async(*args, **kwargs):
    """Same signature as django.core.mail.send_mail. Runs inline when EMAIL_ASYNC is off."""
    if not settings.EMAIL_ASYNC:
        return send_mail(*args, **kwargs)
    _executor.submit(_send, args, kwargs)
    return 1
