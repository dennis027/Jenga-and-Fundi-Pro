# app/permissions.py
from rest_framework.permissions import BasePermission

FUNDI = "01"
CONTRACTOR = "02"


class IsVerified(BasePermission):
    """
    Allows access only to authenticated users whose accounts are active (verified).
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
        )


class IsContractorOrStaff(BasePermission):
    message = "Only contractor accounts can do this."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_staff or u.account_type == CONTRACTOR))


def owns_organization(user, organization):
    return bool(organization) and (user.is_staff or organization.owner_id == user.id)


def visible_gigs(user, queryset=None):
    """Gigs a user may see: staff all, contractors their sites', fundis their own."""
    from .models import Gig
    from django.db.models import Q

    qs = Gig.objects.all() if queryset is None else queryset
    if user.is_staff:
        return qs
    if user.account_type == CONTRACTOR:
        return qs.filter(Q(organization__owner=user) | Q(worker=user))
    return qs.filter(Q(worker=user) | Q(logged_by=user))
