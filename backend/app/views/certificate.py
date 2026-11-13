"""Shareable verified work certificate (signed link; HTML page with QR + JSON)."""
import io
from datetime import timedelta

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.core import signing
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import certificate
from ..permissions import FUNDI


class CertificateLinkView(APIView):
    """GET: a fresh shareable link to the signed-in fundi's work certificate."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.account_type != FUNDI:
            return Response({"detail": "Work certificates are for fundi accounts."}, status=status.HTTP_403_FORBIDDEN)
        token = certificate.make_token(request.user)
        page = request.build_absolute_uri(reverse("certificate-page", args=[token]))
        return Response({
            "url": page,
            "json_url": request.build_absolute_uri(reverse("certificate-json", args=[token])),
            "expires_at": timezone.now() + timedelta(days=settings.CERTIFICATE_MAX_AGE_DAYS),
            "summary": certificate.summary(request.user),
        })


def _load(token):
    try:
        user, _ = certificate.load_user(token)
    except (signing.BadSignature, Exception):
        raise Http404("Certificate not found or expired")
    return user


class CertificateJSONView(APIView):
    """Public, machine-readable certificate (for lenders / employers)."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        user = _load(token)
        return Response({"valid": True, "checked_at": timezone.now(), **certificate.summary(user)})


def certificate_page(request, token):
    user = _load(token)
    url = request.build_absolute_uri()
    buf = io.BytesIO()
    qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8).save(buf)
    return render(request, "certificate/certificate.html", {
        "c": certificate.summary(user),
        "qr_svg": mark_safe(buf.getvalue().decode()),
        "checked_at": timezone.now(),
        "json_url": request.build_absolute_uri(reverse("certificate-json", args=[token])),
    })
