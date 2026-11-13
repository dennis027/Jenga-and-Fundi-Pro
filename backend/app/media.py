"""Serving uploaded files, with ID documents kept private.

Public uploads (profile photos, payment screenshots) are served as before.
Files under MEDIA/verifications/ (national ID photos, selfies) are served only to
staff signed in to the Django admin, or through a short-lived signed URL that
the API hands to the owner/staff (see signed_media_url).
"""
import os

from django.conf import settings
from django.core import signing
from django.http import Http404
from django.views.static import serve

PRIVATE_PREFIXES = ("verifications/",)
_SALT = "app.media.private"


def is_private(name):
    rel = name[len("MEDIA/"):] if name.startswith("MEDIA/") else name
    return rel.startswith(PRIVATE_PREFIXES)


def signed_media_url(field_file, request=None, max_age=None):
    """URL for a stored file; private files get a signature valid for max_age seconds."""
    if not field_file:
        return None
    url = field_file.url
    if is_private(field_file.name) and url.startswith("/"):
        url += "?sig=" + signing.dumps(field_file.name, salt=_SALT)
    return request.build_absolute_uri(url) if request is not None and url.startswith("/") else url


def media_view(request, path):
    if path.startswith(PRIVATE_PREFIXES):
        allowed = request.user.is_authenticated and request.user.is_staff
        if not allowed and request.GET.get("sig"):
            try:
                signed_name = signing.loads(request.GET["sig"], salt=_SALT,
                                            max_age=settings.PRIVATE_MEDIA_URL_MAX_AGE)
                allowed = signed_name == f"MEDIA/{path}"
            except signing.BadSignature:
                allowed = False
        if not allowed:
            raise Http404()
    return serve(request, path, document_root=os.path.join(settings.MEDIA_ROOT, "MEDIA"))
