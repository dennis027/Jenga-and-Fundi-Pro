"""Phone verification by SMS one-time code (Africa's Talking)."""
from django.shortcuts import redirect,render
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import authenticate,get_user_model
from ..serializers import CreditScoreHistorySerializer, GigCompletionRateSerializer, GigCountSerializer, GigRevenueSerializer, GigTrendsSerializer, GigsAvailableSerializer, RegisterSerializer, LoginSerializer, TopGigsSerializer, UserProfileSerializer,GigSerializer,JobTypeSerializer, PaymentSerializer,GigHistorySerializer,OrganizationSerializer,UserSerializer,UserDetailWithGigsSerializer,MpesaNewTransactionSerializer, VerificationRequestSerializer,  WeeklyWorkerReportSerializer,WeeklyGigReportSerializer,JobTypeDistributionSerializer,OrgPerformanceSerializer,VerificationImpactSerializer
from rest_framework import status, permissions,generics
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.utils.timezone import now
from datetime import timedelta
from rest_framework.permissions import IsAuthenticated
from ..models import CreditScoreHistory, Gig, GigsAvailable,JobType,GigHistory, Organization,MpesaNewTransaction,UserPaymentSession,PhoneOTP, VerificationRequest
from rest_framework.parsers import MultiPartParser, FormParser,JSONParser
from django.db.models import Q 
import logging
import base64
from rest_framework.parsers import JSONParser
from datetime import datetime
from django.utils import timezone
from rest_framework.permissions import AllowAny
import pytesseract
from PIL import Image
from django.core.files.storage import default_storage
from django.http import JsonResponse
import re
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
import secrets
from .. import otp as otp_store
from django.db import transaction
from django.utils.crypto import constant_time_compare
from rest_framework.exceptions import PermissionDenied
from ..permissions import IsContractorOrStaff, owns_organization, visible_gigs
from ..scoring import apply_score_change
from ..serializers import GigSearchResultSerializer
from django.core.mail import send_mail
from ..mail import send_mail_async
from ..models import PasswordResetCode
from django.middleware.csrf import get_token
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode
from django.urls import reverse
from django.template.loader import render_to_string
from ..afritesting import send_sms
import africastalking
from django.views import View
import json
from datetime import datetime
from django.db.models import Count, Q, Avg, Sum,Max
from django.db.models.functions import  ExtractWeek, ExtractYear, TruncMonth, TruncYear, TruncWeek
from rest_framework.permissions import AllowAny 
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import api_view, permission_classes
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth






# mpesa credentials
BUSINESS_SHORTCODE = settings.MPESA_SHORTCODE
PASSKEY = settings.MPESA_PASSKEY
CONSUMER_KEY = settings.MPESA_CONSUMER_KEY
CONSUMER_SECRET = settings.MPESA_CONSUMER_SECRET
CALLBACK_URL = settings.MPESA_CALLBACK_URL


logger = logging.getLogger(__name__)


User = get_user_model()


    



    
###########################################################################
###########################################################################
####################END MPESA CIEWS HERE###################################
###########################################################################
###########################################################################


username = settings.AT_USERNAME
api_key = settings.AT_API_KEY  
africastalking.initialize(username, api_key)
sms = africastalking.SMS


def _client_ip(request):
    if settings.CLIENT_IP_HEADER and request.META.get(settings.CLIENT_IP_HEADER):
        return request.META[settings.CLIENT_IP_HEADER].strip()
    if settings.USE_X_FORWARDED_FOR:
        forwarded = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if forwarded:
            return forwarded[0] if settings.XFF_CLIENT_POSITION == "first" else forwarded[-1]
    return request.META.get("REMOTE_ADDR", "")


class SendOTPView(APIView):
    """POST {"phone": "+2547..."} - send a 6-digit code by SMS.

    The code is stored server-side (Redis, hashed, OTP_TTL_SECONDS) and checked
    by VerifyOTPView. It is NOT returned in the response unless the temporary
    OTP_RETURN_CODE_IN_RESPONSE compatibility flag is on.
    """
    permission_classes = [AllowAny]
    authentication_classes = []  # public endpoint: no session, so no CSRF

    def post(self, request):
        phone_number = otp_store.normalize_phone(request.data.get("phone"))
        if not phone_number:
            return JsonResponse({"status": "error", "message": "Phone number is required"}, status=400)

        allowed, retry_after = otp_store.check_send_allowed(phone_number, _client_ip(request))
        if not allowed:
            response = JsonResponse(
                {"status": "error", "message": "Too many OTP requests. Please try again later.",
                 "retry_after": retry_after},
                status=429,
            )
            response["Retry-After"] = str(retry_after)
            return response

        otp = otp_store.issue(phone_number)
        message = f"Your Jenga Pro verification code is {otp}"

        try:
            response = sms.send(message, [phone_number])
        except Exception:
            otp_store.discard(phone_number)
            logger.exception("SMS sending failed")
            return JsonResponse({"status": "error", "message": "Failed to send OTP. Please try again."}, status=502)

        recipients = response.get('SMSMessageData', {}).get('Recipients', [])
        if not recipients:
            otp_store.discard(phone_number)
            logger.error("Africa's Talking returned no recipients: %s", response.get('SMSMessageData', {}).get('Message'))
            return JsonResponse({"status": "error", "message": "Failed to send OTP. Please try again."}, status=502)

        recipient = recipients[0]
        logger.info("OTP SMS: status=%s code=%s message_id=%s",
                    recipient.get('status'), recipient.get('statusCode'), recipient.get('messageId'))

        body = {
            "status": "success",
            "message": "OTP sent",
            "expires_in": settings.OTP_TTL_SECONDS,
            "recipient_status": recipient.get('status'),
            "status_code": recipient.get('statusCode'),
            "message_id": recipient.get('messageId'),
        }
        if settings.OTP_RETURN_CODE_IN_RESPONSE:
            body["otp"] = otp  # legacy clients only - see docs/ARCHITECTURE.md
        return JsonResponse(body)


class VerifyOTPView(APIView):
    """POST {"phone": "+2547...", "otp": "123456"} - check a code from SendOTPView.

    On success returns a phone_token proving the number was verified (used when
    REQUIRE_PHONE_OTP is on).
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        data = request.data
        phone_number = otp_store.normalize_phone(data.get("phone"))
        code = data.get("otp") or data.get("code")
        if not phone_number or not code:
            return JsonResponse({"status": "error", "message": "phone and otp are required"}, status=400)

        result = otp_store.verify(phone_number, code)
        if result == "ok":
            return JsonResponse({"status": "success", "verified": True,
                                 "phone_token": otp_store.issue_phone_token(phone_number),
                                 "phone_token_expires_in": settings.OTP_PHONE_TOKEN_MAX_AGE})
        if result == "locked":
            return JsonResponse({"status": "error", "verified": False,
                                 "message": "Too many attempts. Request a new code."}, status=429)
        if result == "expired":
            return JsonResponse({"status": "error", "verified": False,
                                 "message": "Code expired or not found. Request a new code."}, status=400)
        return JsonResponse({"status": "error", "verified": False, "message": "Invalid code."}, status=400)
