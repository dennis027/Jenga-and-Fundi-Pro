"""Fundi (worker) dashboard and analytics."""
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


#########################################################
#########################################################
#########################################################
# FUNDI DASHBOARD APIS
#########################################################
#########################################################
#########################################################



class FundiDashboardStatsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get dashboard statistics for the authenticated Fundi user
        """
        user = request.user
        print(f"[FundiDashboardStatsView] Authenticated user: {user}, is_authenticated: {user.is_authenticated}")
        
        # Get date ranges
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=30)
        
        # Total gigs for this user
        total_gigs = Gig.objects.filter(worker=user).count()
        
        # Verified gigs
        verified_gigs = Gig.objects.filter(worker=user, is_verified=True).count()
        
        # Count verified days in last 30 days
        verified_days_count = Gig.objects.filter(
            worker=user,
            is_verified=True,
            start_date__gte=thirty_days_ago
        ).values('start_date').distinct().count()
        
        # Verification rate calculation
        verification_rate = round((verified_gigs / total_gigs * 100), 0) if total_gigs > 0 else 0
        
        # Count unique organizations/sites worked
        sites_worked = Gig.objects.filter(worker=user).values('organization').distinct().count()
        
        # Disputes (assuming this would be a separate model - for now set to 0)
        disputes = 0
        
        # Calculate how many months of history (based on earliest gig)
        earliest_gig = Gig.objects.filter(worker=user).order_by('start_date').first()
        history_months = 0
        if earliest_gig:
            delta = today - earliest_gig.start_date
            history_months = max(1, delta.days // 30)
        
        return Response({
            'total_gigs': total_gigs,
            'verified_gigs': verified_gigs,
            'verified_days': verified_days_count,
            'verification_rate': verification_rate,
            'sites_worked': sites_worked,
            'disputes': disputes,
            'history_months': history_months,
            'credit_score': user.credit_score
        })


class FundiRecentWorkLogsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get recent work logs for the authenticated Fundi user
        Limited to last 10 gigs, ordered by most recent
        """
        user = request.user
        print(f"[FundiRecentWorkLogsView] Authenticated user: {user}, is_authenticated: {user.is_authenticated}")
        
        # Get recent gigs with related data
        recent_gigs = Gig.objects.filter(worker=user).select_related(
            'job_type', 'organization', 'verified_by'
        ).order_by('-start_date')[:10]
        
        work_logs = []
        for gig in recent_gigs:
            work_log = {
                'id': gig.id,
                'siteName': gig.organization.name if gig.organization else gig.client_name,
                'jobType': gig.job_type.name,
                'date': gig.start_date.isoformat(),
                'verified': gig.is_verified,
            }
            
            # Add foreman name if verified
            if gig.is_verified and gig.verified_by:
                work_log['foremanName'] = gig.verified_by.full_name or gig.verified_by.username
            
            work_logs.append(work_log)
        
        return Response(work_logs)


class Fundi30DayCalendarView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get 30-day activity calendar showing work status for each day
        """
        user = request.user
        print(f"[Fundi30DayCalendarView] Authenticated user: {user}, is_authenticated: {user.is_authenticated}")
        
        today = timezone.now().date()
        thirty_days_ago = today - timedelta(days=29)
        
        # Get all gigs in the last 30 days
        gigs_in_range = Gig.objects.filter(
            worker=user,
            start_date__gte=thirty_days_ago,
            start_date__lte=today
        ).values('start_date', 'is_verified')
        
        # Create a dict for quick lookup
        gig_status_map = {}
        for gig in gigs_in_range:
            date_key = gig['start_date'].isoformat()
            if date_key not in gig_status_map:
                gig_status_map[date_key] = {
                    'verified': False,
                    'pending': False
                }
            
            if gig['is_verified']:
                gig_status_map[date_key]['verified'] = True
            else:
                gig_status_map[date_key]['pending'] = True
        
        # Build calendar array
        calendar = []
        for i in range(30):
            date = thirty_days_ago + timedelta(days=i)
            date_key = date.isoformat()
            
            # Determine status
            if date_key in gig_status_map:
                if gig_status_map[date_key]['verified']:
                    status = 'verified'
                    tooltip = f"{date.strftime('%b %d')} - Work verified"
                else:
                    status = 'pending'
                    tooltip = f"{date.strftime('%b %d')} - Pending verification"
            else:
                status = 'empty'
                tooltip = f"{date.strftime('%b %d')} - No work logged"
            
            calendar.append({
                'date': date.isoformat(),
                'dayNum': date.day,
                'status': status,
                'tooltip': tooltip
            })
        
        return Response(calendar)


class FundiCreditScoreHistoryView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get credit score history for the authenticated user
        """
        user = request.user
        print(f"[FundiCreditScoreHistoryView] Authenticated user: {user}, is_authenticated: {user.is_authenticated}")
        
        history = CreditScoreHistory.objects.filter(
            user=user
        ).order_by('-timestamp')[:20]
        
        serializer = CreditScoreHistorySerializer(history, many=True)
        return Response(serializer.data)


class FundiAllGigsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get all gigs for the authenticated Fundi user with pagination
        """
        user = request.user
        print(f"[FundiAllGigsView] Authenticated user: {user}, is_authenticated: {user.is_authenticated}")
        
        gigs = Gig.objects.filter(worker=user).select_related(
            'job_type', 'organization', 'verified_by'
        ).order_by('-start_date')
        
        serializer = GigSerializer(gigs, many=True)
        return Response(serializer.data)


class FundiOrganizationsWorkedView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Get list of organizations the Fundi has worked with
        """
        user = request.user
        print(f"[FundiOrganizationsWorkedView] Authenticated user: {user}, is_authenticated: {user.is_authenticated}")
        
        organizations = Organization.objects.filter(
            gigs__worker=user
        ).distinct().values('id', 'name', 'county', 'constituency', 'ward')
        
        return Response(list(organizations))
    

############################################################
############################################################
###### Fundi Pro analytics #################################
############################################################
#############################################################



class FundiWorkTrendsView(APIView):
    """
    Get work trends over time for a Fundi worker (daily, weekly, monthly)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        period = request.GET.get('period', 'weekly')  # daily, weekly, monthly
        days = int(request.GET.get('days', 30))
        
        start_date = timezone.now().date() - timedelta(days=days)
        
        if period == 'daily':
            gigs_by_period = Gig.objects.filter(
                worker=user,
                start_date__gte=start_date
            ).annotate(
                period=TruncDate('start_date')
            ).values('period').annotate(
                total_gigs=Count('id'),
                verified_gigs=Count('id', filter=Q(is_verified=True)),
                total_earnings=Sum('amount_paid')
            ).order_by('period')
            
        elif period == 'weekly':
            gigs_by_period = Gig.objects.filter(
                worker=user,
                start_date__gte=start_date
            ).annotate(
                period=TruncWeek('start_date')
            ).values('period').annotate(
                total_gigs=Count('id'),
                verified_gigs=Count('id', filter=Q(is_verified=True)),
                total_earnings=Sum('amount_paid')
            ).order_by('period')
            
        else:  # monthly
            gigs_by_period = Gig.objects.filter(
                worker=user,
                start_date__gte=start_date
            ).annotate(
                period=TruncMonth('start_date')
            ).values('period').annotate(
                total_gigs=Count('id'),
                verified_gigs=Count('id', filter=Q(is_verified=True)),
                total_earnings=Sum('amount_paid')
            ).order_by('period')
        
        trends = []
        for item in gigs_by_period:
            trends.append({
                'period': item['period'].isoformat(),
                'total_gigs': item['total_gigs'],
                'verified_gigs': item['verified_gigs'],
                'total_earnings': float(item['total_earnings'] or 0),
                'verification_rate': round((item['verified_gigs'] / item['total_gigs'] * 100), 1) if item['total_gigs'] > 0 else 0
            })
        
        return Response({
            'period_type': period,
            'days': days,
            'trends': trends
        })


class FundiOrganizationPerformanceView(APIView):
    """
    Get performance metrics for organizations the Fundi has worked with
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        org_performance = Gig.objects.filter(
            worker=user
        ).values(
            'organization__id',
            'organization__name'
        ).annotate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            completed_gigs=Count('id', filter=Q(is_complete=True)),
            total_earnings=Sum('amount_paid'),
            avg_earnings=Avg('amount_paid')
        ).order_by('-total_gigs')
        
        performance = []
        for org in org_performance:
            verification_rate = round((org['verified_gigs'] / org['total_gigs'] * 100), 1) if org['total_gigs'] > 0 else 0
            completion_rate = round((org['completed_gigs'] / org['total_gigs'] * 100), 1) if org['total_gigs'] > 0 else 0
            
            performance.append({
                'organization_id': org['organization__id'],
                'organization_name': org['organization__name'],
                'total_gigs': org['total_gigs'],
                'verified_gigs': org['verified_gigs'],
                'completed_gigs': org['completed_gigs'],
                'verification_rate': verification_rate,
                'completion_rate': completion_rate,
                'total_earnings': float(org['total_earnings'] or 0),
                'avg_earnings': float(org['avg_earnings'] or 0)
            })
        
        return Response(performance)


class FundiJobTypeAnalyticsView(APIView):
    """
    Get analytics by job type for the Fundi
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        job_type_stats = Gig.objects.filter(
            worker=user
        ).values(
            'job_type__id',
            'job_type__name'
        ).annotate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_earnings=Sum('amount_paid'),
            avg_earnings_per_gig=Avg('amount_paid')
        ).order_by('-total_gigs')
        
        analytics = []
        for job in job_type_stats:
            analytics.append({
                'job_type_id': job['job_type__id'],
                'job_type': job['job_type__name'],
                'total_gigs': job['total_gigs'],
                'verified_gigs': job['verified_gigs'],
                'total_earnings': float(job['total_earnings'] or 0),
                'avg_earnings_per_gig': float(job['avg_earnings_per_gig'] or 0),
                'verification_rate': round((job['verified_gigs'] / job['total_gigs'] * 100), 1) if job['total_gigs'] > 0 else 0
            })
        
        return Response(analytics)


class FundiCreditScoreAnalyticsView(APIView):
    """
    Get detailed credit score history and analytics
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Current credit score
        current_score = user.credit_score
        
        # Credit score history (last 30 entries)
        score_history = CreditScoreHistory.objects.filter(
            user=user
        ).order_by('-timestamp')[:30]
        
        history_data = []
        for entry in score_history:
            history_data.append({
                'timestamp': entry.timestamp.isoformat(),
                'action': entry.get_action_display(),
                'change': entry.change,
                'new_score': entry.new_score
            })
        
        # Score breakdown by action type
        score_breakdown = CreditScoreHistory.objects.filter(
            user=user
        ).values('action').annotate(
            count=Count('id'),
            total_change=Sum('change'),
            avg_change=Avg('change')
        )
        
        breakdown_data = []
        for item in score_breakdown:
            breakdown_data.append({
                'action': item['action'],
                'count': item['count'],
                'total_change': item['total_change'],
                'avg_change': round(float(item['avg_change'] or 0), 1)
            })
        
        # Score trend (last 7 days)
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_changes = CreditScoreHistory.objects.filter(
            user=user,
            timestamp__gte=seven_days_ago
        ).aggregate(
            total_change=Sum('change'),
            num_changes=Count('id')
        )
        
        return Response({
            'current_score': current_score,
            'score_history': history_data,
            'score_breakdown': breakdown_data,
            'recent_trend': {
                'last_7_days_change': recent_changes['total_change'] or 0,
                'num_changes': recent_changes['num_changes'] or 0
            }
        })


class FundiEarningsAnalyticsView(APIView):
    """
    Get earnings analytics and projections
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Overall earnings stats
        earnings_stats = Gig.objects.filter(
            worker=user
        ).aggregate(
            total_earnings=Sum('amount_paid'),
            avg_gig_value=Avg('amount_paid'),
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True))
        )
        
        # Earnings by month (last 12 months)
        twelve_months_ago = timezone.now().date() - timedelta(days=365)
        monthly_earnings = Gig.objects.filter(
            worker=user,
            start_date__gte=twelve_months_ago
        ).annotate(
            month=TruncMonth('start_date')
        ).values('month').annotate(
            earnings=Sum('amount_paid'),
            gigs=Count('id'),
            verified=Count('id', filter=Q(is_verified=True))
        ).order_by('month')
        
        monthly_data = []
        for item in monthly_earnings:
            monthly_data.append({
                'month': item['month'].strftime('%Y-%m'),
                'earnings': float(item['earnings'] or 0),
                'gigs': item['gigs'],
                'verified': item['verified'],
                'avg_per_gig': float(item['earnings'] / item['gigs']) if item['gigs'] > 0 else 0
            })
        
        return Response({
            'total_earnings': float(earnings_stats['total_earnings'] or 0),
            'avg_gig_value': float(earnings_stats['avg_gig_value'] or 0),
            'total_gigs': earnings_stats['total_gigs'],
            'verified_gigs': earnings_stats['verified_gigs'],
            'monthly_breakdown': monthly_data
        })


class FundiLocationAnalyticsView(APIView):
    """
    Get analytics by work location (county, constituency, ward)
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        level = request.GET.get('level', 'county')  # county, constituency, ward
        
        if level == 'county':
            location_field = 'county'
        elif level == 'constituency':
            location_field = 'constituency'
        else:
            location_field = 'ward'
        
        location_stats = Gig.objects.filter(
            worker=user
        ).values(location_field).annotate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_earnings=Sum('amount_paid')
        ).order_by('-total_gigs')
        
        analytics = []
        for loc in location_stats:
            analytics.append({
                'location': loc[location_field],
                'total_gigs': loc['total_gigs'],
                'verified_gigs': loc['verified_gigs'],
                'total_earnings': float(loc['total_earnings'] or 0),
                'verification_rate': round((loc['verified_gigs'] / loc['total_gigs'] * 100), 1) if loc['total_gigs'] > 0 else 0
            })
        
        return Response({
            'level': level,
            'analytics': analytics
        })


class FundiVerificationMetricsView(APIView):
    """
    Get detailed verification metrics for the Fundi
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Overall verification stats
        total_gigs = Gig.objects.filter(worker=user).count()
        verified_gigs = Gig.objects.filter(worker=user, is_verified=True).count()
        pending_gigs = total_gigs - verified_gigs
        
        # Verification rate over time (last 30 days)
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        daily_verification = Gig.objects.filter(
            worker=user,
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
        org_verification = Gig.objects.filter(
            worker=user
        ).values(
            'organization__name'
        ).annotate(
            total=Count('id'),
            verified=Count('id', filter=Q(is_verified=True))
        ).order_by('-total')
        
        org_rates = []
        for org in org_verification:
            rate = round((org['verified'] / org['total'] * 100), 1) if org['total'] > 0 else 0
            org_rates.append({
                'organization': org['organization__name'],
                'total_gigs': org['total'],
                'verified_gigs': org['verified'],
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


class FundiWorkConsistencyView(APIView):
    """
    Get work consistency and activity metrics
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Work activity by period
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        sixty_days_ago = timezone.now().date() - timedelta(days=60)
        ninety_days_ago = timezone.now().date() - timedelta(days=90)
        
        gigs_30_days = Gig.objects.filter(
            worker=user,
            start_date__gte=thirty_days_ago
        ).count()
        
        gigs_60_days = Gig.objects.filter(
            worker=user,
            start_date__gte=sixty_days_ago
        ).count()
        
        gigs_90_days = Gig.objects.filter(
            worker=user,
            start_date__gte=ninety_days_ago
        ).count()
        
        # Organizations worked with
        orgs_worked = Gig.objects.filter(
            worker=user
        ).values('organization').distinct().count()
        
        orgs_recent = Gig.objects.filter(
            worker=user,
            start_date__gte=thirty_days_ago
        ).values('organization').distinct().count()
        
        # Job type diversity
        job_types_count = Gig.objects.filter(
            worker=user
        ).values('job_type').distinct().count()
        
        # Consistency score (gigs per month average)
        months_active = Gig.objects.filter(
            worker=user
        ).dates('start_date', 'month').count()
        
        total_gigs = Gig.objects.filter(worker=user).count()
        consistency_score = round((total_gigs / months_active), 1) if months_active > 0 else 0
        
        # Determine activity level
        if gigs_30_days >= 8:
            activity_level = 'high'
        elif gigs_30_days >= 4:
            activity_level = 'medium'
        elif gigs_30_days >= 1:
            activity_level = 'low'
        else:
            activity_level = 'inactive'
        
        return Response({
            'work_frequency': {
                'last_30_days': gigs_30_days,
                'last_60_days': gigs_60_days,
                'last_90_days': gigs_90_days
            },
            'organizations': {
                'total_worked_with': orgs_worked,
                'active_last_30_days': orgs_recent
            },
            'diversity': {
                'job_types_count': job_types_count,
                'months_active': months_active
            },
            'consistency': {
                'gigs_per_month_avg': consistency_score,
                'activity_level': activity_level
            }
        })


class FundiComparativeAnalyticsView(APIView):
    """
    Compare current period vs previous period for Fundi
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        days = int(request.GET.get('days', 30))
        
        today = timezone.now().date()
        current_start = today - timedelta(days=days)
        previous_start = current_start - timedelta(days=days)
        previous_end = current_start - timedelta(days=1)
        
        # Current period stats
        current_stats = Gig.objects.filter(
            worker=user,
            start_date__gte=current_start
        ).aggregate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_earnings=Sum('amount_paid'),
            unique_orgs=Count('organization', distinct=True)
        )
        
        # Previous period stats
        previous_stats = Gig.objects.filter(
            worker=user,
            start_date__gte=previous_start,
            start_date__lte=previous_end
        ).aggregate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_earnings=Sum('amount_paid'),
            unique_orgs=Count('organization', distinct=True)
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
                'total_earnings': float(current_stats['total_earnings'] or 0),
                'unique_orgs': current_stats['unique_orgs']
            },
            'previous_period': {
                'total_gigs': previous_stats['total_gigs'],
                'verified_gigs': previous_stats['verified_gigs'],
                'total_earnings': float(previous_stats['total_earnings'] or 0),
                'unique_orgs': previous_stats['unique_orgs']
            },
            'changes': {
                'gigs_change': calc_change(current_stats['total_gigs'], previous_stats['total_gigs']),
                'verified_change': calc_change(current_stats['verified_gigs'], previous_stats['verified_gigs']),
                'earnings_change': calc_change(
                    float(current_stats['total_earnings'] or 0),
                    float(previous_stats['total_earnings'] or 0)
                ),
                'orgs_change': calc_change(current_stats['unique_orgs'], previous_stats['unique_orgs'])
            }
        })


class FundiSummaryDashboardView(APIView):
    """
    Get comprehensive summary for Fundi analytics dashboard
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        # Time periods
        today = timezone.now().date()
        seven_days_ago = today - timedelta(days=7)
        thirty_days_ago = today - timedelta(days=30)
        
        # Overall metrics
        all_time = Gig.objects.filter(worker=user).aggregate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_earnings=Sum('amount_paid'),
            unique_orgs=Count('organization', distinct=True)
        )
        
        # Last 7 days
        last_7_days = Gig.objects.filter(
            worker=user,
            start_date__gte=seven_days_ago
        ).aggregate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_earnings=Sum('amount_paid')
        )
        
        # Last 30 days
        last_30_days = Gig.objects.filter(
            worker=user,
            start_date__gte=thirty_days_ago
        ).aggregate(
            total_gigs=Count('id'),
            verified_gigs=Count('id', filter=Q(is_verified=True)),
            total_earnings=Sum('amount_paid')
        )
        
        # Top performing organization
        top_org = Gig.objects.filter(
            worker=user
        ).values(
            'organization__name'
        ).annotate(
            gigs=Count('id'),
            earnings=Sum('amount_paid')
        ).order_by('-gigs').first()
        
        # Top earning job type
        top_job = Gig.objects.filter(
            worker=user
        ).values(
            'job_type__name'
        ).annotate(
            gigs=Count('id'),
            earnings=Sum('amount_paid')
        ).order_by('-earnings').first()
        
        return Response({
            'all_time': {
                'total_gigs': all_time['total_gigs'],
                'verified_gigs': all_time['verified_gigs'],
                'verification_rate': round((all_time['verified_gigs'] / all_time['total_gigs'] * 100), 1) if all_time['total_gigs'] > 0 else 0,
                'total_earnings': float(all_time['total_earnings'] or 0),
                'unique_orgs': all_time['unique_orgs'],
                'credit_score': user.credit_score
            },
            'last_7_days': {
                'total_gigs': last_7_days['total_gigs'],
                'verified_gigs': last_7_days['verified_gigs'],
                'total_earnings': float(last_7_days['total_earnings'] or 0)
            },
            'last_30_days': {
                'total_gigs': last_30_days['total_gigs'],
                'verified_gigs': last_30_days['verified_gigs'],
                'total_earnings': float(last_30_days['total_earnings'] or 0)
            },
            'top_performers': {
                'top_organization': top_org['organization__name'] if top_org else None,
                'top_organization_gigs': top_org['gigs'] if top_org else 0,
                'top_organization_earnings': float(top_org['earnings'] or 0) if top_org else 0,
                'top_job_type': top_job['job_type__name'] if top_job else None,
                'top_job_type_gigs': top_job['gigs'] if top_job else 0,
                'top_job_type_earnings': float(top_job['earnings'] or 0) if top_job else 0
            }
        })
