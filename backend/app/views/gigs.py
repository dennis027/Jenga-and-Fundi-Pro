"""Gigs, sites (organizations), job types, gig history, worker search."""
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


class LogGigView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        #Only Fundi can log gigs
        if request.user.account_type != '01':
            return Response(
                {"detail": "Only Fundi accounts can log gigs."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = GigSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(
                worker=request.user,
                logged_by=request.user
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# 2. Confirm/Verify a gig by peer or foreman  
def verify_gig(user, gig_id):
    """Verify one gig as `user`. Returns (http_status, body). Shared by single and bulk verify."""
    with transaction.atomic():
        gig = Gig.objects.select_for_update().select_related("organization", "job_type", "worker").filter(id=gig_id).first()
        if not gig:
            return status.HTTP_404_NOT_FOUND, {"detail": "Gig not found."}
        if not owns_organization(user, gig.organization):
            return status.HTTP_403_FORBIDDEN, {"detail": "Only the contractor who owns this site can verify its gigs."}
        if user.id in (gig.logged_by_id, gig.worker_id):
            return status.HTTP_403_FORBIDDEN, {"detail": "You cannot verify your own gig."}
        if gig.is_verified:
            return status.HTTP_200_OK, {"message": "Gig already verified.", "gig_status": "verified",
                                        "gig": GigSerializer(gig).data}
        gig.is_verified = True
        gig.verified_by = user
        gig.save(update_fields=["is_verified", "verified_by"])
        new_score = apply_score_change(gig.worker, "verify_gig")

    from ..inbox import log, push
    trade = gig.job_type.name if gig.job_type_id else 'gig'
    push(gig.worker, "gig_verified", f"{gig.organization.name} verified your {trade}",
         f"+5 points, score now {new_score}. Mark it complete when done.", "/main-menu/gig-summary",
         sms_text=f"{gig.organization.name} verified your {trade}. +5 points, score now {new_score}. Mark it complete when done.")
    log(user, gig.organization, "gig_verified", f"Verified {gig.worker.full_name or gig.worker.username}'s {trade} gig")
    return status.HTTP_200_OK, {"message": "Gig verified successfully.", "gig_status": "verified",
                                "gig": GigSerializer(gig).data, "worker_credit_score": new_score}


class VerifyGigView(APIView):
    """Only the contractor who owns the gig's site (or staff) can verify it."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, gig_id):
        code, body = verify_gig(request.user, gig_id)
        return Response(body, status=code)


@method_decorator(csrf_exempt, name='dispatch')
class CompleteGigAPIView(APIView):
    """The gig's worker, its site's contractor, or staff can complete a verified gig (once)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, gig_id):
        with transaction.atomic():
            try:
                gig = Gig.objects.select_for_update().select_related("organization").get(id=gig_id)
            except Gig.DoesNotExist:
                return Response({"error": "Gig not found"}, status=status.HTTP_404_NOT_FOUND)

            if not (request.user.id == gig.worker_id or owns_organization(request.user, gig.organization)):
                return Response({"error": "You cannot complete this gig."}, status=status.HTTP_403_FORBIDDEN)
            if not gig.is_verified:
                return Response({"error": "Gig must be verified before marking as complete"},
                                status=status.HTTP_400_BAD_REQUEST)

            gig_history = GigHistory.objects.create(
                worker=gig.worker,
                job_type=gig.job_type,
                start_date=gig.start_date,
                duration_value=gig.duration_value,
                duration_unit=gig.duration_unit,
                client_name=gig.client_name or gig.organization.name,
                client_phone=gig.client_phone or "",
                county=gig.county,
                constituency=gig.constituency,
                ward=gig.ward,
                is_verified=gig.is_verified,
                organization=gig.organization,
                amount_paid=gig.amount_paid,
            )
            new_score = apply_score_change(gig.worker, "complete_gig")
            gig.delete()
        from ..inbox import log
        log(request.user, gig_history.organization, "gig_completed",
            f"{gig_history.worker.full_name or gig_history.worker.username} completed {gig_history.job_type.name}")

        return Response({
            "message": "Gig moved to history successfully",
            "history_id": gig_history.id,
            "new_score": new_score,
        }, status=status.HTTP_200_OK)


class CreditScoreHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        history = CreditScoreHistory.objects.filter(user=request.user).order_by("timestamp")
        return Response(CreditScoreHistorySerializer(history, many=True).data)





#SEARCH GIGS

class GigSearchView(APIView):
    """Search all gigs. Client phone and amounts are hidden on gigs that are not yours."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        county = request.query_params.get('county')
        constituency = request.query_params.get('constituency')
        ward = request.query_params.get('ward')
        job_type = request.query_params.get('job_type')  # ID of JobType
        client_name = request.query_params.get('client_name')

        gigs = Gig.objects.select_related("organization")
        if county:
            gigs = gigs.filter(county__icontains=county)
        if constituency:
            gigs = gigs.filter(constituency__icontains=constituency)
        if ward:
            gigs = gigs.filter(ward__icontains=ward)
        if job_type:
            gigs = gigs.filter(job_type_id=job_type)
        if client_name:
            gigs = gigs.filter(client_name__icontains=client_name)

        mine = set(visible_gigs(request.user, gigs).values_list("id", flat=True))
        data = [GigSerializer(g).data if g.id in mine else GigSearchResultSerializer(g).data for g in gigs]
        return Response(data, status=status.HTTP_200_OK)


class GigListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        gigs = visible_gigs(request.user)
        
        serializer = GigSerializer(gigs, many=True)
        return Response(serializer.data)
    


class GigsAvailableListCreateView(generics.ListCreateAPIView):
    serializer_class = GigsAvailableSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Open job posts at active sites; ?mine=1 -> the signed-in contractor's own posts.
        qs = GigsAvailable.objects.select_related("organization").order_by('-created_at')
        if self.request.query_params.get("mine"):
            return qs.filter(organization__owner=self.request.user)
        return qs.filter(organization__is_active=True, is_open=True)

    def perform_create(self, serializer):
        org_id = self.request.data.get("organization")
        try:
            organization = Organization.objects.get(id=org_id, owner=self.request.user)
        except Organization.DoesNotExist:
            raise PermissionDenied("You do not own this organization or it does not exist.")
        
        post = serializer.save(organization=organization)
        from ..inbox import job_post_alerts, log
        log(self.request.user, organization, "job_posted", f"Posted job '{post.title}'")
        job_post_alerts(post)

class UserOrganizationGigListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        #  Only Contractor can view org gigs
        if request.user.account_type != '02':
            return Response(
                {"detail": "Only Contractor accounts can view organization gigs."},
                status=status.HTTP_403_FORBIDDEN
            )

        gigs = Gig.objects.filter(
            organization__owner=request.user   # gigs in my orgs
        ).exclude(
            logged_by=request.user            # exclude gigs I logged myself
        ).select_related('organization', 'job_type', 'worker')

        serializer = GigSerializer(gigs, many=True)
        return Response(serializer.data)

class LoggedByUserGigListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        gigs = Gig.objects.filter(logged_by=request.user)
        serializer = GigSerializer(gigs, many=True)
        return Response(serializer.data)
    


class JobTypeListCreateView(generics.ListCreateAPIView):
    """Anyone signed in can list job types (optionally ?organization=<id>);
    only the site's contractor can add one."""
    permission_classes = [IsAuthenticated]
    serializer_class = JobTypeSerializer

    def get_queryset(self):
        qs = JobType.objects.all()
        org = self.request.query_params.get("organization")
        return qs.filter(organization_id=org) if org else qs

    def perform_create(self, serializer):
        org = serializer.validated_data.get("organization")
        if not owns_organization(self.request.user, org):
            raise PermissionDenied("You can only add job types to your own sites.")
        serializer.save()


class JobTypeDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            job_type = JobType.objects.select_related("organization").get(pk=pk)
        except JobType.DoesNotExist:
            return Response({"error": "Job type not found."}, status=status.HTTP_404_NOT_FOUND)
        if not owns_organization(request.user, job_type.organization):
            return Response({"error": "You can only delete job types of your own sites."},
                            status=status.HTTP_403_FORBIDDEN)
        job_type.delete()
        return Response({"message": "Job type deleted."}, status=status.HTTP_204_NO_CONTENT)
    


class GigHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # get only history belonging to the logged-in user
        histories = GigHistory.objects.filter(worker=request.user).order_by('-created_at')
        serializer = GigHistorySerializer(histories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    


# single organization gigs view
class OrganizationGigsAPIView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, org_id):
        try:
            organization = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization not found'}, status=status.HTTP_404_NOT_FOUND)
        if not owns_organization(request.user, organization):
            return Response({'error': 'You can only view gigs of your own sites.'}, status=status.HTTP_403_FORBIDDEN)

        gigs = Gig.objects.filter(organization=organization)
        serializer = GigSerializer(gigs, many=True)
        return Response(serializer.data)



class UserGigHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        histories = GigHistory.objects.filter(worker=request.user)
        serializer = GigHistorySerializer(histories, many=True)
        return Response(serializer.data)
    


# organization model

class OrganizationListCreateView(generics.ListCreateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Organization.objects.all().order_by("id")

    def create(self, request, *args, **kwargs):
        #  Only Contractor can create organization
        if request.user.account_type != '02':
            return Response(
                {"detail": "Only Contractor accounts can create organizations."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

#user organization list view
class UserOrganizationListCreateView(generics.ListCreateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only return organizations owned by the logged-in user
        return Organization.objects.filter(owner=self.request.user).order_by("id")

    def create(self, request, *args, **kwargs):
        # Only Contractor can create organization
        if request.user.account_type != '02':
            return Response(
                {"detail": "Only Contractor accounts can create organizations."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class OrganizationDetailUpdateView(generics.RetrieveUpdateAPIView):
    serializer_class = OrganizationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        return Organization.objects.filter(owner=self.request.user)

class OrganizationSoftDeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            organization = Organization.objects.get(pk=pk, owner=request.user)
            organization.is_active = not organization.is_active
            organization.save()
            return Response({
                "status": "success",
                "message": f"Organization is_active set to {organization.is_active}"
            })
        except Organization.DoesNotExist:
            return Response({"error": "Organization not found"}, status=status.HTTP_404_NOT_FOUND)
        


class WorkerSearchAPIView(APIView):
    """Contractors (and staff) look up a worker by username, email, phone, national ID or name."""
    permission_classes = [IsContractorOrStaff]

    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q', None)
        if not query:
            return Response({"error": "Please provide a search query (?q=)"}, status=status.HTTP_400_BAD_REQUEST)

        exact = Q(username__iexact=query) | Q(email__iexact=query) | Q(phone__iexact=query) | Q(national_id__iexact=query)
        user = (User.objects.filter(exact).first()
                or User.objects.filter(full_name__icontains=query).order_by("id").first())
        if not user:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        data = UserDetailWithGigsSerializer(user).data
        # Gigs at other contractors' sites: no client phone / pay / verifier details.
        mine = set(visible_gigs(request.user, Gig.objects.filter(worker=user)).values_list("id", flat=True))
        data["gigs"] = [GigSerializer(g).data if g.id in mine else GigSearchResultSerializer(g).data
                        for g in Gig.objects.filter(worker=user).select_related("job_type", "organization")]
        data["logged_gigs"] = []
        from ..models import GigHistory, GigRating
        from django.db.models import Avg, Count
        agg = GigRating.objects.filter(history__worker=user).aggregate(avg=Avg("stars"), n=Count("id"))
        data["completed_gigs"] = GigHistory.objects.filter(worker=user, is_verified=True).count()
        data["rating_avg"] = round(agg["avg"], 1) if agg["avg"] else None
        data["ratings_count"] = agg["n"]
        from .workforce import _worker_card
        card = _worker_card(user, request.user)
        for k in ("skills", "years_experience", "day_rate", "bio", "is_available", "available_from", "in_crew"):
            data[k] = card[k]
        return Response(data, status=status.HTTP_200_OK)



class GigsAvailableDeleteView(APIView):
    """DELETE a job post (owner of its site, or staff)."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        post = GigsAvailable.objects.select_related("organization").filter(pk=pk).first()
        if not post:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not owns_organization(request.user, post.organization):
            return Response({"detail": "You can only remove posts for your own sites."}, status=status.HTTP_403_FORBIDDEN)
        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
