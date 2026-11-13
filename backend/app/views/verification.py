"""Identity verification requests (national ID + selfie) and staff review."""
from .. import identity
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


# 1. Submit Verification (User uploads ID front, back, selfie)
class VerificationRequestCreateView(generics.CreateAPIView):
    serializer_class = VerificationRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        request = serializer.save(user=self.request.user)
        # link to user
        self.request.user.current_verification = request
        self.request.user.save()


# 2. Approve/Reject Verification (Admin only)
from rest_framework.views import APIView

class VerificationActionView(APIView):
    """Staff only. Points are awarded once, on the first approval."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        try:
            verification = VerificationRequest.objects.select_related("user").get(pk=pk)
        except VerificationRequest.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        action = request.data.get("action")
        reason = request.data.get("reason", "")
        user = verification.user

        # Same rules as the Django admin actions (app/identity.py).
        if action == "approve":
            identity.approve(verification)
        elif action == "reject":
            identity.reject(verification, reason)
        else:
            return Response({"error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(VerificationRequestSerializer(verification).data)


class VerificationRequestListView(generics.ListAPIView):
    serializer_class = VerificationRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:  # Admin can see all
            return VerificationRequest.objects.all()
        return VerificationRequest.objects.filter(user=user)

# user view for latest verification
class LatestVerificationView(generics.RetrieveAPIView):


    serializer_class = VerificationRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        latest_verification = (
            VerificationRequest.objects.filter(user=request.user)
            .order_by("-created_at")
            .first()
        )

        if not latest_verification:
            return Response({"detail": "No verification found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(latest_verification)
        return Response(serializer.data)
