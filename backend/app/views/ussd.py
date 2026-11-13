"""Africa's Talking USSD menu for fundis without smartphones.

    1. My credit score   2. Recent verified gigs   3. Identity verification status

Africa's Talking does not sign callbacks, so the callback URL must carry
?token=USSD_CALLBACK_TOKEN; the endpoint is disabled while the token is unset.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..models import Gig, GigHistory

MENU = "CON Fundi Pro\n1. My credit score\n2. Recent verified gigs\n3. ID verification status"


def _phone_variants(phone):
    p = (phone or "").replace(" ", "")
    local = "0" + p[4:] if p.startswith("+254") else p
    return {p, local, "+254" + local[1:] if local.startswith("0") else p}


def _reply(text):
    return HttpResponse(text, content_type="text/plain; charset=utf-8")


@csrf_exempt
@require_POST
def ussd_callback(request):
    token = settings.USSD_CALLBACK_TOKEN
    if not token or not constant_time_compare(request.GET.get("token", ""), token):
        return HttpResponse(status=403)

    text = request.POST.get("text", "")
    user = get_user_model().objects.filter(phone__in=_phone_variants(request.POST.get("phoneNumber"))).first()
    if user is None:
        return _reply("END This phone number is not linked to a Fundi Pro account.")
    if text == "":
        return _reply(MENU)
    if text == "1":
        return _reply(f"END {user.full_name or user.username}: credit score {user.credit_score or 0}/100.")
    if text == "2":
        rows = list(GigHistory.objects.filter(worker=user, is_verified=True).select_related("job_type")
                    .order_by("-start_date")[:3]) + list(Gig.objects.filter(worker=user, is_verified=True)
                                                         .select_related("job_type").order_by("-start_date")[:3])
        rows = sorted(rows, key=lambda g: g.start_date, reverse=True)[:3]
        if not rows:
            return _reply("END No verified gigs yet.")
        lines = [f"{g.start_date:%d %b}: {g.job_type.name}, {g.duration_value} {g.duration_unit}" for g in rows]
        return _reply("END Recent verified gigs:\n" + "\n".join(lines))
    if text == "3":
        v = user.current_verification
        state = {"approved": "approved", "pending": "under review", "rejected": "rejected"}.get(v.status if v else "", "not submitted")
        return _reply(f"END ID verification: {state}.")
    return _reply("END Invalid choice.")
