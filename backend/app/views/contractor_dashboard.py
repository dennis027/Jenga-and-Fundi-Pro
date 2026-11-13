"""Contractor dashboard and analytics."""
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


############################################################
############################################################
############################################################
# JENGA PRO DASHBOARD
############################################################
############################################################
############################################################


class ContractorDashboardStatsView(APIView):
    """
    Get dashboard statistics for Contractor/Supervisor
    Only shows data for organizations owned by the authenticated user
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(f"[ContractorDashboardStatsView] User: {user}, Account type: {user.account_type}")
        
        # Get date ranges
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # Get user's organizations
        user_orgs = Organization.objects.filter(owner=user)
        
        # Total gigs in user's organizations
        total_gigs = Gig.objects.filter(organization__in=user_orgs).count()
        
        # Unverified gigs
        unverified_gigs = Gig.objects.filter(
            organization__in=user_orgs,
            is_verified=False
        ).count()
        
        # Active workers (unique workers who have worked in user's orgs)
        active_workers = Gig.objects.filter(
            organization__in=user_orgs
        ).values('worker').distinct().count()
        
        # Active sites (user's organizations)
        active_sites = user_orgs.filter(is_active=True).count()
        
        # Verified this week
        verified_this_week = Gig.objects.filter(
            organization__in=user_orgs,
            is_verified=True,
            created_at__gte=week_ago
        ).count()
        
        # Verification rate
        verified_gigs = Gig.objects.filter(
            organization__in=user_orgs,
            is_verified=True
        ).count()
        verification_rate = round((verified_gigs / total_gigs * 100), 0) if total_gigs > 0 else 0
        
        # Average verification time (days between created_at and when verified)
        # For now, we'll use a placeholder. You might want to add a verified_at field
        avg_verification_time = 4  # placeholder
        
        return Response({
            'total_gigs': total_gigs,
            'unverified_gigs': unverified_gigs,
            'active_workers': active_workers,
            'active_sites': active_sites,
            'verified_this_week': verified_this_week,
            'verification_rate': verification_rate,
            'avg_verification_time': avg_verification_time
        })


class ContractorRecentGigsView(APIView):
    """
    Get recent gigs for Contractor's organizations
    Limited to last 20 gigs, ordered by most recent
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(f"[ContractorRecentGigsView] User: {user}")
        
        # Get user's organizations
        user_orgs = Organization.objects.filter(owner=user)
        
        # Get recent gigs in user's organizations
        recent_gigs = Gig.objects.filter(
            organization__in=user_orgs
        ).select_related(
            'worker', 'job_type', 'organization'
        ).order_by('-created_at')[:20]
        
        gigs_data = []
        for gig in recent_gigs:
            gigs_data.append({
                'id': gig.id,
                'workerName': gig.worker.full_name or gig.worker.username,
                'siteName': gig.organization.name,
                'jobType': gig.job_type.name,
                'date': gig.start_date.strftime('%b %d, %Y'),
                'verified': gig.is_verified
            })
        
        return Response(gigs_data)


class ContractorWeeklyChartView(APIView):
    """
    Get weekly gig counts for the last 7 days
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(f"[ContractorWeeklyChartView] User: {user}")
        
        # Get user's organizations
        user_orgs = Organization.objects.filter(owner=user)
        
        # Get last 7 days
        today = timezone.now().date()
        weekly_data = []
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            
            # Count gigs for this day
            gigs_count = Gig.objects.filter(
                organization__in=user_orgs,
                start_date=date
            ).count()
            
            weekly_data.append({
                'day': day_names[date.weekday()],
                'gigs': gigs_count,
                'date': date.isoformat()
            })
        
        # Calculate max for chart scaling
        max_gigs = max([day['gigs'] for day in weekly_data]) if weekly_data else 0
        
        return Response({
            'weekly_data': weekly_data,
            'max_weekly_gigs': max_gigs
        })

class ContractorTopSitesView(APIView):
    """
    Get top performing sites/organizations for the contractor
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(f"[ContractorTopSitesView] User: {user}")
        
        # Get user's organizations with gig counts
        # Use different names to avoid conflict with @property methods
        user_orgs = Organization.objects.filter(owner=user).annotate(
            gigs_total=Count('gigs'),
            gigs_verified=Count('gigs', filter=Q(gigs__is_verified=True)),
            workers_count=Count('gigs__worker', distinct=True)
        ).order_by('-gigs_total')[:10]
        
        sites_data = []
        for org in user_orgs:
            # Calculate completion rate (verified / total)
            completion = round((org.gigs_verified / org.gigs_total * 100), 0) if org.gigs_total > 0 else 0
            
            sites_data.append({
                'id': org.id,
                'name': org.name,
                'workers': org.workers_count,
                'gigs': org.gigs_total,
                'completion': completion
            })
        
        return Response(sites_data)


class ContractorTopWorkersView(APIView):
    """
    Get top performing workers across contractor's organizations
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(f"[ContractorTopWorkersView] User: {user}")
        
        # Get user's organizations
        user_orgs = Organization.objects.filter(owner=user)
        
        # Get workers with their gig counts in user's organizations
        workers_data = Gig.objects.filter(
            organization__in=user_orgs
        ).values(
            'worker__id',
            'worker__username',
            'worker__full_name',
            'worker__profile_pic',
            'worker__credit_score'
        ).annotate(
            gigs_count=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True))
        ).order_by('-gigs_count')[:10]
        
        top_workers = []
        for rank, worker in enumerate(workers_data, start=1):
            # Calculate rating from credit score (scale to 5.0)
            credit_score = worker['worker__credit_score'] or 0
            rating = round((credit_score / 100) * 5, 1)
            
            top_workers.append({
                'id': worker['worker__id'],
                'rank': rank,
                'name': worker['worker__full_name'] or worker['worker__username'],
                'avatar': worker['worker__profile_pic'] or '',
                'gigs': worker['gigs_count'],
                'rating': rating,
                'credit_score': credit_score
            })
        
        return Response(top_workers)


class Contractor7DayCalendarView(APIView):
    """
    Get 7-day calendar with gig counts for mobile view
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(f"[Contractor7DayCalendarView] User: {user}")
        
        # Get user's organizations
        user_orgs = Organization.objects.filter(owner=user)
        
        # Get last 7 days
        today = timezone.now().date()
        calendar = []
        day_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            
            # Count gigs for this day
            gigs_count = Gig.objects.filter(
                organization__in=user_orgs,
                start_date=date
            ).count()
            
            calendar.append({
                'date': date.isoformat(),
                'dayName': day_names[date.weekday()],
                'dayNum': date.day,
                'gigs': gigs_count
            })
        
        return Response(calendar)
    

class ContractorOrganizationsView(APIView):
    """
    Get all organizations owned by the contractor
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(f"[ContractorOrganizationsView] User: {user}")
        
        # Get user's organizations with stats
        # Use different names to avoid conflict with @property methods
        organizations = Organization.objects.filter(owner=user).annotate(
            gigs_total=Count('gigs'),
            gigs_verified=Count('gigs', filter=Q(gigs__is_verified=True)),
            workers_count=Count('gigs__worker', distinct=True)
        ).order_by('-created_at')
        
        orgs_data = []
        for org in organizations:
            orgs_data.append({
                'id': org.id,
                'name': org.name,
                'description': org.description,
                'county': org.county,
                'constituency': org.constituency,
                'ward': org.ward,
                'phone_number': org.phone_number,
                'is_active': org.is_active,
                'created_at': org.created_at.isoformat(),
                'total_gigs': org.gigs_total,
                'verified_gigs': org.gigs_verified,
                'unique_workers': org.workers_count
            })
        
        return Response(orgs_data)
    

    
class ContractorGigsByOrganizationView(APIView):
    """
    Get gigs filtered by organization
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, org_id):
        user = request.user
        print(f"[ContractorGigsByOrganizationView] User: {user}, Org ID: {org_id}")
        
        # Verify organization belongs to user
        try:
            organization = Organization.objects.get(id=org_id, owner=user)
        except Organization.DoesNotExist:
            return Response({'error': 'Organization not found'}, status=404)
        
        # Get gigs for this organization
        gigs = Gig.objects.filter(
            organization=organization
        ).select_related(
            'worker', 'job_type', 'verified_by'
        ).order_by('-created_at')
        
        serializer = GigSerializer(gigs, many=True)
        return Response(serializer.data)


class ContractorUnverifiedGigsView(APIView):
    """
    Get all unverified gigs across contractor's organizations
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(f"[ContractorUnverifiedGigsView] User: {user}")
        
        # Get user's organizations
        user_orgs = Organization.objects.filter(owner=user)
        
        # Get unverified gigs
        unverified_gigs = Gig.objects.filter(
            organization__in=user_orgs,
            is_verified=False
        ).select_related(
            'worker', 'job_type', 'organization'
        ).order_by('-created_at')
        
        gigs_data = []
        for gig in unverified_gigs:
            gigs_data.append({
                'id': gig.id,
                'workerName': gig.worker.full_name or gig.worker.username,
                'workerUsername': gig.worker.username,
                'workerPhone': gig.worker.phone,
                'siteName': gig.organization.name,
                'jobType': gig.job_type.name,
                'startDate': gig.start_date.isoformat(),
                'duration': f"{gig.duration_value} {gig.duration_unit}",
                'location': f"{gig.county}, {gig.constituency}, {gig.ward}",
                'createdAt': gig.created_at.isoformat()
            })
        
        return Response(gigs_data)





#################################################################
#################################################################
#################JENGA PRO ANALYTICS#############################
#################################################################
#################################################################


class ContractorGigTrendsView(APIView):
    """
    Get gig trends over time (daily, weekly, monthly)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        period = request.GET.get('period', 'weekly')  # daily, weekly, monthly
        days = int(request.GET.get('days', 30))
        
        user_orgs = Organization.objects.filter(owner=user)
        start_date = timezone.now().date() - timedelta(days=days)
        
        if period == 'daily':
            gigs_by_period = Gig.objects.filter(
                organization__in=user_orgs,
                start_date__gte=start_date
            ).annotate(
                period=TruncDate('start_date')
            ).values('period').annotate(
                total_gigs=Count('id'),
                verified_gigs=Count('id', filter=Q(is_verified=True)),
                total_revenue=Sum('amount_paid')
            ).order_by('period')
            
        elif period == 'weekly':
            gigs_by_period = Gig.objects.filter(
                organization__in=user_orgs,
                start_date__gte=start_date
            ).annotate(
                period=TruncWeek('start_date')
            ).values('period').annotate(
                total_gigs=Count('id'),
                verified_gigs=Count('id', filter=Q(is_verified=True)),
                total_revenue=Sum('amount_paid')
            ).order_by('period')
            
        else:  # monthly
            gigs_by_period = Gig.objects.filter(
                organization__in=user_orgs,
                start_date__gte=start_date
            ).annotate(
                period=TruncMonth('start_date')
            ).values('period').annotate(
                total_gigs=Count('id'),
                verified_gigs=Count('id', filter=Q(is_verified=True)),
                total_revenue=Sum('amount_paid')
            ).order_by('period')
        
        trends = []
        for item in gigs_by_period:
            trends.append({
                'period': item['period'].isoformat(),
                'total_gigs': item['total_gigs'],
                'verified_gigs': item['verified_gigs'],
                'total_revenue': float(item['total_revenue'] or 0),
                'verification_rate': round((item['verified_gigs'] / item['total_gigs'] * 100), 1) if item['total_gigs'] > 0 else 0
            })
        
        return Response({
            'period_type': period,
            'days': days,
            'trends': trends
        })


class ContractorWorkerPerformanceView(APIView):
    """
    Get detailed worker performance metrics
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_orgs = Organization.objects.filter(owner=user)
        
        workers = Gig.objects.filter(
            organization__in=user_orgs
        ).values(
            'worker__id',
            'worker__username',
            'worker__full_name',
            'worker__credit_score'
        ).annotate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            completed_gigs=Count('id', filter=Q(is_complete=True)),
            total_earnings=Sum('amount_paid'),
            avg_gig_value=Avg('amount_paid')
        ).order_by('-total_gigs')
        
        performance = []
        for worker in workers:
            verification_rate = round((worker['verified_gigs'] / worker['total_gigs'] * 100), 1) if worker['total_gigs'] > 0 else 0
            completion_rate = round((worker['completed_gigs'] / worker['total_gigs'] * 100), 1) if worker['total_gigs'] > 0 else 0
            
            performance.append({
                'worker_id': worker['worker__id'],
                'worker_name': worker['worker__full_name'] or worker['worker__username'],
                'total_gigs': worker['total_gigs'],
                'verified_gigs': worker['verified_gigs'],
                'completed_gigs': worker['completed_gigs'],
                'verification_rate': verification_rate,
                'completion_rate': completion_rate,
                'total_earnings': float(worker['total_earnings'] or 0),
                'avg_gig_value': float(worker['avg_gig_value'] or 0),
                'credit_score': worker['worker__credit_score']
            })
        
        return Response(performance)


class ContractorJobTypeAnalyticsView(APIView):
    """
    Get analytics by job type
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_orgs = Organization.objects.filter(owner=user)
        
        job_type_stats = Gig.objects.filter(
            organization__in=user_orgs
        ).values(
            'job_type__id',
            'job_type__name'
        ).annotate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            unique_workers=Count('worker', distinct=True),
            total_revenue=Sum('amount_paid'),
            avg_revenue_per_gig=Avg('amount_paid')
        ).order_by('-total_gigs')
        
        analytics = []
        for job in job_type_stats:
            analytics.append({
                'job_type_id': job['job_type__id'],
                'job_type': job['job_type__name'],
                'total_gigs': job['total_gigs'],
                'verified_gigs': job['verified_gigs'],
                'unique_workers': job['unique_workers'],
                'total_revenue': float(job['total_revenue'] or 0),
                'avg_revenue_per_gig': float(job['avg_revenue_per_gig'] or 0),
                'verification_rate': round((job['verified_gigs'] / job['total_gigs'] * 100), 1) if job['total_gigs'] > 0 else 0
            })
        
        return Response(analytics)


class ContractorOrganizationPerformanceView(APIView):
    """
    Get detailed performance metrics for each organization
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        orgs = Organization.objects.filter(owner=user).annotate(
            gigs_total=Count('gigs'),
            gigs_verified=Count('gigs', filter=Q(gigs__is_verified=True)),
            gigs_completed=Count('gigs', filter=Q(gigs__is_complete=True)),
            workers_count=Count('gigs__worker', distinct=True),
            revenue_total=Sum('gigs__amount_paid'),
            revenue_avg=Avg('gigs__amount_paid')
        )
        
        performance = []
        for org in orgs:
            verification_rate = round((org.gigs_verified / org.gigs_total * 100), 1) if org.gigs_total > 0 else 0
            completion_rate = round((org.gigs_completed / org.gigs_total * 100), 1) if org.gigs_total > 0 else 0
            
            performance.append({
                'organization_id': org.id,
                'organization_name': org.name,
                'location': f"{org.county}, {org.constituency}",
                'total_gigs': org.gigs_total,
                'verified_gigs': org.gigs_verified,
                'completed_gigs': org.gigs_completed,
                'verification_rate': verification_rate,
                'completion_rate': completion_rate,
                'unique_workers': org.workers_count,
                'total_revenue': float(org.revenue_total or 0),
                'avg_revenue_per_gig': float(org.revenue_avg or 0),
                'is_active': org.is_active
            })
        
        return Response(performance)


class ContractorRevenueAnalyticsView(APIView):
    """
    Get revenue analytics and projections
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_orgs = Organization.objects.filter(owner=user)
        
        # Overall revenue stats
        revenue_stats = Gig.objects.filter(
            organization__in=user_orgs
        ).aggregate(
            total_revenue=Sum('amount_paid'),
            avg_gig_value=Avg('amount_paid'),
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True))
        )
        
        # Revenue by month (last 12 months)
        twelve_months_ago = timezone.now().date() - timedelta(days=365)
        monthly_revenue = Gig.objects.filter(
            organization__in=user_orgs,
            start_date__gte=twelve_months_ago
        ).annotate(
            month=TruncMonth('start_date')
        ).values('month').annotate(
            revenue=Sum('amount_paid'),
            gigs=Count('id')
        ).order_by('month')
        
        monthly_data = []
        for item in monthly_revenue:
            monthly_data.append({
                'month': item['month'].strftime('%Y-%m'),
                'revenue': float(item['revenue'] or 0),
                'gigs': item['gigs'],
                'avg_per_gig': float(item['revenue'] / item['gigs']) if item['gigs'] > 0 else 0
            })
        
        return Response({
            'total_revenue': float(revenue_stats['total_revenue'] or 0),
            'avg_gig_value': float(revenue_stats['avg_gig_value'] or 0),
            'total_gigs': revenue_stats['total_gigs'],
            'verified_gigs': revenue_stats['verified_gigs'],
            'monthly_breakdown': monthly_data
        })


class ContractorLocationAnalyticsView(APIView):
    """
    Get analytics by location (county, constituency, ward)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_orgs = Organization.objects.filter(owner=user)
        level = request.GET.get('level', 'county')  # county, constituency, ward
        
        if level == 'county':
            location_field = 'county'
        elif level == 'constituency':
            location_field = 'constituency'
        else:
            location_field = 'ward'
        
        location_stats = Gig.objects.filter(
            organization__in=user_orgs
        ).values(location_field).annotate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            unique_workers=Count('worker', distinct=True),
            total_revenue=Sum('amount_paid')
        ).order_by('-total_gigs')
        
        analytics = []
        for loc in location_stats:
            analytics.append({
                'location': loc[location_field],
                'total_gigs': loc['total_gigs'],
                'verified_gigs': loc['verified_gigs'],
                'unique_workers': loc['unique_workers'],
                'total_revenue': float(loc['total_revenue'] or 0),
                'verification_rate': round((loc['verified_gigs'] / loc['total_gigs'] * 100), 1) if loc['total_gigs'] > 0 else 0
            })
        
        return Response({
            'level': level,
            'analytics': analytics
        })


class ContractorVerificationMetricsView(APIView):
    """
    Get detailed verification metrics
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_orgs = Organization.objects.filter(owner=user)
        
        # Overall verification stats
        total_gigs = Gig.objects.filter(organization__in=user_orgs).count()
        verified_gigs = Gig.objects.filter(organization__in=user_orgs, is_verified=True).count()
        pending_gigs = total_gigs - verified_gigs
        
        # Verification rate over time (last 30 days)
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        daily_verification = Gig.objects.filter(
            organization__in=user_orgs,
            start_date__gte=thirty_days_ago
        ).annotate(
            day=TruncDate('start_date')
        ).values('day').annotate(
            total=Count('id'),
            verified=Count('id', filter=Q(is_verified=True))
        ).order_by('day')
        
        daily_rates = []
        for item in daily_verification:
            rate = round((item['verified'] / item['total'] * 100), 1) if item['total'] > 0 else 0
            daily_rates.append({
                'date': item['day'].isoformat(),
                'total_gigs': item['total'],
                'verified_gigs': item['verified'],
                'verification_rate': rate
            })
        
        # Verification by organization
        org_verification = Organization.objects.filter(owner=user).annotate(
            total=Count('gigs'),
            verified=Count('gigs', filter=Q(gigs__is_verified=True))
        ).order_by('-total')
        
        org_rates = []
        for org in org_verification:
            rate = round((org.verified / org.total * 100), 1) if org.total > 0 else 0
            org_rates.append({
                'organization': org.name,
                'total_gigs': org.total,
                'verified_gigs': org.verified,
                'verification_rate': rate
            })
        
        return Response({
            'overall': {
                'total_gigs': total_gigs,
                'verified_gigs': verified_gigs,
                'pending_gigs': pending_gigs,
                'verification_rate': round((verified_gigs / total_gigs * 100), 1) if total_gigs > 0 else 0
            },
            'daily_trends': daily_rates,
            'by_organization': org_rates
        })


class ContractorWorkerRetentionView(APIView):
    """
    Get worker retention and engagement metrics
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # ✅ Contractor only
        if user.account_type != '02':
            return Response(
                {"detail": "Only Contractor accounts can access this data."},
                status=403
            )

        user_orgs = Organization.objects.filter(owner=user)

        # Time periods
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        sixty_days_ago = today - timedelta(days=60)
        ninety_days_ago = today - timedelta(days=90)

        # -------------------------
        # Active workers by period
        # -------------------------
        active_30_days = Gig.objects.filter(
            organization__in=user_orgs,
            start_date__gte=thirty_days_ago
        ).values('worker').distinct().count()

        active_60_days = Gig.objects.filter(
            organization__in=user_orgs,
            start_date__gte=sixty_days_ago
        ).values('worker').distinct().count()

        active_90_days = Gig.objects.filter(
            organization__in=user_orgs,
            start_date__gte=ninety_days_ago
        ).values('worker').distinct().count()

        # -------------------------
        # Worker engagement levels
        # -------------------------
        worker_engagement = Gig.objects.filter(
            organization__in=user_orgs
        ).values(
            'worker__id',
            'worker__full_name',
            'worker__username'
        ).annotate(
            total_gigs=Count('id'),
            recent_gigs=Count('id', filter=Q(start_date__gte=thirty_days_ago)),
            last_gig_date=Max('start_date')  # ✅ use Max instead of F
        ).order_by('-total_gigs')

        engagement_data = []
        for worker in worker_engagement:
            # Calculate engagement level
            if worker['recent_gigs'] >= 4:
                engagement = 'high'
            elif worker['recent_gigs'] >= 2:
                engagement = 'medium'
            elif worker['recent_gigs'] >= 1:
                engagement = 'low'
            else:
                engagement = 'inactive'

            engagement_data.append({
                'worker_id': worker['worker__id'],
                'worker_name': worker['worker__full_name'] or worker['worker__username'],
                'total_gigs': worker['total_gigs'],
                'recent_gigs_30d': worker['recent_gigs'],
                'last_gig_date': worker['last_gig_date'],
                'engagement_level': engagement
            })

        return Response({
            'active_workers': {
                'last_30_days': active_30_days,
                'last_60_days': active_60_days,
                'last_90_days': active_90_days
            },
            'worker_engagement': engagement_data
        })
    

class ContractorComparativeAnalyticsView(APIView):
    """
    Compare current period vs previous period
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_orgs = Organization.objects.filter(owner=user)
        days = int(request.GET.get('days', 30))
        
        today = timezone.now().date()
        current_start = today - timedelta(days=days)
        previous_start = current_start - timedelta(days=days)
        previous_end = current_start - timedelta(days=1)
        
        # Current period stats
        current_stats = Gig.objects.filter(
            organization__in=user_orgs,
            start_date__gte=current_start
        ).aggregate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_revenue=Sum('amount_paid'),
            unique_workers=Count('worker', distinct=True)
        )
        
        # Previous period stats
        previous_stats = Gig.objects.filter(
            organization__in=user_orgs,
            start_date__gte=previous_start,
            start_date__lte=previous_end
        ).aggregate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_revenue=Sum('amount_paid'),
            unique_workers=Count('worker', distinct=True)
        )
        
        # Calculate percentage changes
        def calc_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous * 100), 1)
        
        return Response({
            'period_days': days,
            'current_period': {
                'total_gigs': current_stats['total_gigs'],
                'verified_gigs': current_stats['verified_gigs'],
                'total_revenue': float(current_stats['total_revenue'] or 0),
                'unique_workers': current_stats['unique_workers']
            },
            'previous_period': {
                'total_gigs': previous_stats['total_gigs'],
                'verified_gigs': previous_stats['verified_gigs'],
                'total_revenue': float(previous_stats['total_revenue'] or 0),
                'unique_workers': previous_stats['unique_workers']
            },
            'changes': {
                'gigs_change': calc_change(current_stats['total_gigs'], previous_stats['total_gigs']),
                'verified_change': calc_change(current_stats['verified_gigs'], previous_stats['verified_gigs']),
                'revenue_change': calc_change(
                    float(current_stats['total_revenue'] or 0),
                    float(previous_stats['total_revenue'] or 0)
                ),
                'workers_change': calc_change(current_stats['unique_workers'], previous_stats['unique_workers'])
            }
        })



class ContractorSummaryDashboardView(APIView):
    """
    Get comprehensive summary for analytics dashboard
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # ✅ Contractor only
        if user.account_type != '02':
            return Response(
                {"detail": "Only Contractor accounts can access this dashboard."},
                status=403
            )

        user_orgs = Organization.objects.filter(owner=user)

        # Time periods
        today = timezone.now().date()
        seven_days_ago = today - timedelta(days=7)
        thirty_days_ago = today - timedelta(days=30)

        # -------------------------
        # Overall metrics
        # -------------------------
        all_time = Gig.objects.filter(
            organization__in=user_orgs
        ).aggregate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_revenue=Sum('amount_paid'),
            unique_workers=Count('worker', distinct=True)
        )

        # -------------------------
        # Last 7 days
        # -------------------------
        last_7_days = Gig.objects.filter(
            organization__in=user_orgs,
            start_date__gte=seven_days_ago
        ).aggregate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_revenue=Sum('amount_paid')
        )

        # -------------------------
        # Last 30 days
        # -------------------------
        last_30_days = Gig.objects.filter(
            organization__in=user_orgs,
            start_date__gte=thirty_days_ago
        ).aggregate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_revenue=Sum('amount_paid')
        )

        # -------------------------
        # Top worker
        # -------------------------
        top_worker = Gig.objects.filter(
            organization__in=user_orgs
        ).values(
            'worker__full_name',
            'worker__username'
        ).annotate(
            gigs=Count('id')
        ).order_by('-gigs').first()

        # -------------------------
        # Top organization (FIXED)
        # -------------------------
        top_org = Organization.objects.filter(owner=user).annotate(
            gig_count=Count('gigs')  # ✅ renamed from gigs
        ).order_by('-gig_count').first()

        # -------------------------
        # Safe calculations
        # -------------------------
        total_gigs = all_time['total_gigs'] or 0
        verified_gigs = all_time['verified_gigs'] or 0

        verification_rate = (
            round((verified_gigs / total_gigs * 100), 1)
            if total_gigs > 0 else 0
        )

        # -------------------------
        # Response
        # -------------------------
        return Response({
            'all_time': {
                'total_gigs': total_gigs,
                'verified_gigs': verified_gigs,
                'verification_rate': verification_rate,
                'total_revenue': float(all_time['total_revenue'] or 0),
                'unique_workers': all_time['unique_workers'] or 0
            },

            'last_7_days': {
                'total_gigs': last_7_days['total_gigs'] or 0,
                'verified_gigs': last_7_days['verified_gigs'] or 0,
                'total_revenue': float(last_7_days['total_revenue'] or 0)
            },

            'last_30_days': {
                'total_gigs': last_30_days['total_gigs'] or 0,
                'verified_gigs': last_30_days['verified_gigs'] or 0,
                'total_revenue': float(last_30_days['total_revenue'] or 0)
            },

            'top_performers': {
                'top_worker': (
                    (top_worker['worker__full_name'] or
                     top_worker['worker__username'])
                    if top_worker else None
                ),
                'top_worker_gigs': top_worker['gigs'] if top_worker else 0,
                'top_organization': top_org.name if top_org else None,
                'top_organization_gigs': top_org.gig_count if top_org else 0
            }
        })
