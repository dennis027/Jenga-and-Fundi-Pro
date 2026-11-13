"""Platform-wide reports (staff) and gig analysis."""
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


    




############################################
############################################
###############REPORTS VIEWS################
############################################
############################################



# 1. Weekly Worker Report
class WeeklyWorkerReportView(APIView):
    permission_classes = [permissions.IsAdminUser]  # platform-wide report

    def get(self, request):
        qs = (
            Gig.objects
            .annotate(year=ExtractYear("created_at"), week=ExtractWeek("created_at"))
            .values("year", "week")
            .annotate(
                total_workers=Count("worker", distinct=True),
                verified_workers=Count("worker", distinct=True, filter=Q(worker__is_verified=True)),
                unverified_workers=Count("worker", distinct=True, filter=Q(worker__is_verified=False)),
            )
            .order_by("-year", "-week")
        )
        data = [
            {
                "week": f"{row['year']}-W{row['week']}",
                "total_workers": row["total_workers"],
                "verified_workers": row["verified_workers"],
                "unverified_workers": row["unverified_workers"],
            }
            for row in qs
        ]
        return Response(WeeklyWorkerReportSerializer(data, many=True).data)


# 2. Weekly Gigs Report
class WeeklyGigReportView(APIView):
    permission_classes = [permissions.IsAdminUser]  # platform-wide report

    def get(self, request):
        qs = (
            Gig.objects
            .annotate(year=ExtractYear("created_at"), week=ExtractWeek("created_at"))
            .values("year", "week")
            .annotate(
                total_gigs=Count("id"),
                verified=Count("id", filter=Q(is_verified=True)),
                unverified=Count("id", filter=Q(is_verified=False)),
            )
            .order_by("-year", "-week")
        )
        data = [
            {
                "week": f"{row['year']}-W{row['week']}",
                "total_gigs": row["total_gigs"],
                "verified": row["verified"],
                "unverified": row["unverified"],
            }
            for row in qs
        ]
        return Response(WeeklyGigReportSerializer(data, many=True).data)


# 3. Job Type Distribution Report
class JobTypeDistributionReportView(APIView):
    permission_classes = [permissions.IsAdminUser]  # platform-wide report

    def get(self, request):
        qs = (
            Gig.objects
            .annotate(year=ExtractYear("created_at"), week=ExtractWeek("created_at"))
            .values("year", "week", "job_type__name")
            .annotate(count=Count("id"))
            .order_by("-year", "-week", "-count")
        )
        data = [
            {
                "week": f"{row['year']}-W{row['week']}",
                "job_type": row["job_type__name"],
                "count": row["count"],
            }
            for row in qs
        ]
        return Response(JobTypeDistributionSerializer(data, many=True).data)


# 4. Organization Performance Report
class OrgPerformanceReportView(APIView):
    permission_classes = [permissions.IsAdminUser]  # platform-wide report

    def get(self, request):
        qs = (
            Gig.objects
            .values("organization__name")
            .annotate(
                total_gigs=Count("id"),
                verified=Count("id", filter=Q(is_verified=True)),
            )
            .order_by("-total_gigs")
        )
        data = [
            {
                "organization": row["organization__name"],
                "total_gigs": row["total_gigs"],
                "verified": row["verified"],
            }
            for row in qs
        ]
        return Response(OrgPerformanceSerializer(data, many=True).data)


# 5. Verification Impact Report
class VerificationImpactReportView(APIView):

    permission_classes = [permissions.IsAdminUser]  # platform-wide report

    def get(self, request):
        verified_workers = User.objects.filter(is_verified=True).annotate(gig_count=Count("gigs"))
        unverified_workers = User.objects.filter(is_verified=False).annotate(gig_count=Count("gigs"))

        data = {
            "verified_workers_count": verified_workers.count(),
            "verified_avg_gigs": verified_workers.aggregate(avg=Avg("gig_count"))["avg"] or 0,
            "unverified_workers_count": unverified_workers.count(),
            "unverified_avg_gigs": unverified_workers.aggregate(avg=Avg("gig_count"))["avg"] or 0,
        }
        return Response(VerificationImpactSerializer(data).data)
    




##############################################################
##############################################################
##########  SINGLE USER GIGS AND HISTORY VIEWS ###############
##############################################################
##############################################################

# 1. Gig count analysis
class GigCountAnalysisView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_orgs = Organization.objects.filter(owner=request.user)
        gigs = Gig.objects.filter(organization__in=user_orgs)

        period = request.query_params.get("period", "week")

        if period == "day":
            start_date = now().date() - timedelta(days=1)
        elif period == "month":
            start_date = now().date() - timedelta(days=30)
        elif period == "year":
            start_date = now().date() - timedelta(days=365)
        else:  # default week
            start_date = now().date() - timedelta(days=7)

        count = gigs.filter(start_date__gte=start_date).count()
        data = {"period": period, "total_gigs": count}
        return Response(GigCountSerializer(data).data)


# 2. Gig completion rate
class GigCompletionRateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # All orgs owned by the user
        user_orgs = Organization.objects.filter(owner=request.user)

        # Current gigs
        gigCurrents = Gig.objects.filter(organization__in=user_orgs)

        # Completed gigs (automatically in history)
        gigHist = GigHistory.objects.filter(organization__in=user_orgs)

        total = gigCurrents.count() + gigHist.count()
        completed = gigHist.count()
        rate = (completed / total * 100) if total > 0 else 0

        data = {
            "total_gigs": total,
            "completed_gigs": completed,
            "completion_rate": round(rate, 2),
        }
        return Response(data)


# 3. Total revenue per period
class GigRevenueAnalysisView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_orgs = Organization.objects.filter(owner=request.user)
        gigs = Gig.objects.filter(organization__in=user_orgs)

        period = request.query_params.get("period", "week")

        if period == "day":
            start_date = now().date() - timedelta(days=1)
        elif period == "month":
            start_date = now().date() - timedelta(days=30)
        elif period == "year":
            start_date = now().date() - timedelta(days=365)
        else:  # default week
            start_date = now().date() - timedelta(days=7)

        total = gigs.filter(start_date__gte=start_date).aggregate(
            total=Sum("amount_paid")
        )["total"] or 0

        data = {"period": period, "total_revenue": total}
        return Response(GigRevenueSerializer(data).data)


# 4. Gig trends (weekly, monthly, yearly)
class GigTrendsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        period = request.query_params.get("period", "week")
        user_orgs = Organization.objects.filter(owner=request.user)
        gigs = Gig.objects.filter(organization__in=user_orgs, is_complete=True)

        if period == "week":
            grouping = TruncWeek("start_date")
        elif period == "month":
            grouping = TruncMonth("start_date")
        elif period == "year":
            grouping = TruncYear("start_date")
        else:
            return Response(
                {"error": "Invalid period. Use week, month, or year."}, status=400
            )

        trends = (
            gigs.annotate(period=grouping)
            .values("period")
            .annotate(completed_gigs=Count("id"))
            .order_by("period")
        )

        return Response(GigTrendsSerializer(trends, many=True).data)


# 5. Top earning gigs
class TopEarningGigsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_orgs = Organization.objects.filter(owner=request.user)
        gigs = Gig.objects.filter(organization__in=user_orgs)

        top_gigs = (
            gigs.values("job_type__name", "client_name")
            .annotate(revenue=Sum("amount_paid"))
            .order_by("-revenue")[:5]
        )

        data = [
            {
                "gig_title": g["job_type__name"] or g["client_name"] or "Unknown",
                "revenue": g["revenue"],
            }
            for g in top_gigs
        ]
        return Response(TopGigsSerializer(data, many=True).data)
