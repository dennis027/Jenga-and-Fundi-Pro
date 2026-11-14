"""In-app notifications (the bell) and the contractor activity log.

push() never raises: a failed notification must not fail the action that caused it.
"""
import logging

logger = logging.getLogger(__name__)


def push(user, kind, title, body="", link="", sms_text=None):
    """Store a notification for `user`; optionally also send an SMS (if SMS alerts are on)."""
    from .models import Notification
    if not user:
        return None
    try:
        n = Notification.objects.create(user=user, kind=kind, title=title[:200], body=(body or "")[:300], link=link[:200])
    except Exception:
        logger.exception("notification failed")
        return None
    if sms_text:
        from .notify import sms
        sms(user, sms_text)
    return n


def log(actor, organization, action, summary):
    from .models import ActivityLog
    try:
        return ActivityLog.objects.create(actor=actor if getattr(actor, "pk", None) else None,
                                          organization=organization, action=action, summary=summary[:300])
    except Exception:
        logger.exception("activity log failed")
        return None


def job_post_alerts(post):
    """Notify fundis whose job alerts match a new job post. Returns how many were notified."""
    from .models import JobAlert
    text = f"{post.title} {post.description or ''}".lower()
    seen = set()
    for a in JobAlert.objects.select_related("user").filter(user__is_active=True):
        if a.user_id in seen:
            continue
        if a.county and a.county.lower() != (post.county or "").lower():
            continue
        if a.keyword and a.keyword.lower() not in text:
            continue
        seen.add(a.user_id)
        where = ", ".join(x for x in (post.ward, post.county) if x)
        push(a.user, "job_alert", f"New job: {post.title}", f"{post.organization.name} · {where}",
             "/main-menu/search-gigs",
             sms_text=f"New job near you: {post.title[:60]} at {post.organization.name}. Open Fundi Pro to apply." if a.sms else None)
    return len(seen)
