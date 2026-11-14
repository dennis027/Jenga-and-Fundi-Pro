from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken  
from .models import  CreditScoreHistory, User,Gig,JobType,Payment,GigHistory,Organization,MpesaNewTransaction, VerificationRequest, GigsAvailable  # use your custom user model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'confirm_password',
            'account_type', 'full_name', 'national_id', 'county', 'constituency', 'ward', 'phone'
        ]
        extra_kwargs = {'password': {'write_only': True}}

    def validate_phone(self, value):
        _require_phone_otp(self, value)
        return value

    def validate_email(self, value):
        # Allow unverified users to pass; view handles EMAIL_NOT_VERIFIED
        return value

    def validate_username(self, value):
        return value

    def validate(self, data):
        if data['password'] != data.get('confirm_password', ''):
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return data

    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.is_verified = False
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()



class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Add custom claims
        token['username'] = user.username
        token['account_type'] = user.account_type  # Add this line

        return token
    

# app/serializers.py


def _require_phone_otp(serializer, phone, current=None):
    """With REQUIRE_PHONE_OTP, a new phone number needs a valid phone_token from /verify-otp/."""
    from django.conf import settings
    from . import otp
    if not settings.REQUIRE_PHONE_OTP or not phone:
        return
    if current and otp.normalize_phone(current) == otp.normalize_phone(phone):
        return
    if not otp.phone_token_valid(serializer.initial_data.get("phone_token"), phone):
        raise serializers.ValidationError("Verify this phone number with the SMS code first (phone_token missing or expired).")


def _id_verified(user):
    v = getattr(user, "current_verification", None)
    return bool(v and v.status == "approved")


class GigSerializer(serializers.ModelSerializer):
    job_type_name = serializers.CharField(source="job_type.name", read_only=True, default=None)
    organization_name = serializers.CharField(source="organization.name", read_only=True, default=None)
    worker_name = serializers.SerializerMethodField()

    def get_worker_name(self, obj):
        w = obj.worker
        return (w.full_name or w.username) if w else None

    worker_username = serializers.CharField(source="worker.username", read_only=True, default=None)

    class Meta:
        model = Gig
        fields = '__all__'
        read_only_fields = [
            'worker',
            'logged_by',
            'verified_by',
            'is_verified',
            'created_at',
            'client_name',
            'client_phone',
            'county',
            'constituency',
            'ward',
        ]

    def create(self, validated_data):
        organization = validated_data.get('organization')

        if not organization:
            raise serializers.ValidationError({
                "organization": "Organization is required"
            })

       
        validated_data['client_name'] = organization.name
        validated_data['client_phone'] = organization.phone_number
        validated_data['county'] = organization.county
        validated_data['constituency'] = organization.constituency
        validated_data['ward'] = organization.ward

        return super().create(validated_data)



class UserProfileSerializer(serializers.ModelSerializer):
    id_verified = serializers.SerializerMethodField(help_text="Identity documents approved by staff.")

    def get_id_verified(self, obj):
        return _id_verified(obj)

    class Meta:
        model = User
        fields = ['username', 'email', 'phone', 'full_name', 'national_id',   'county', 'constituency', 'ward', 'profile_pic','is_verified','credit_score','current_verification', 'id_verified',
                  'skills', 'years_experience', 'day_rate', 'bio', 'is_available', 'available_from']
        # Trust fields are only changed by the platform (scoring / ID verification).
        read_only_fields = ['username', 'is_verified', 'credit_score', 'current_verification']

    def validate_phone(self, value):
        user = self.instance  # the currently authenticated user
        if User.objects.filter(phone__iexact=value).exclude(pk=user.pk).exists():
            raise serializers.ValidationError("Phone number is already in use.")
        _require_phone_otp(self, value, current=user.phone if user else None)
        return value
        
class JobTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobType
        fields = ['id', 'name', 'code', 'organization']
        read_only_fields = ['code']


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'
        read_only_fields = ['user', 'payment_date', 'is_confirmed']

    def validate_transaction_code(self, value):
        code = (value or "").strip().upper()
        if Payment.objects.filter(transaction_code__iexact=code).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("This M-Pesa code has already been uploaded.")
        return code

    def to_representation(self, instance):
        # Payment screenshots show names and phone numbers: signed, short-lived links only.
        from .media import signed_media_url
        data = super().to_representation(instance)
        data["screenshot"] = signed_media_url(instance.screenshot, self.context.get("request"))
        return data



class GigHistorySerializer(serializers.ModelSerializer):
    job_type_name = serializers.CharField(source="job_type.name", read_only=True, default=None)
    organization_name = serializers.CharField(source="organization.name", read_only=True, default=None)
    worker_name = serializers.SerializerMethodField()

    def get_worker_name(self, obj):
        w = obj.worker
        return (w.full_name or w.username) if w else None

    worker_username = serializers.CharField(source="worker.username", read_only=True, default=None)

    class Meta:
        model = GigHistory
        fields = '__all__'
        read_only_fields = ['worker']



class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'
        read_only_fields = ['owner', 'created_at']

class CreditScoreHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditScoreHistory
        fields = ["id", "change", "new_score", "action", "timestamp"]

class UserDetailWithGigsSerializer(serializers.ModelSerializer):
    gigs = GigSerializer(many=True, read_only=True)  # worker gigs
    logged_gigs = GigSerializer(many=True, read_only=True)  # gigs logged by this user

    id_verified = serializers.SerializerMethodField(help_text="Identity documents approved by staff.")

    def get_id_verified(self, obj):
        return _id_verified(obj)

    class Meta:
        model = User
        fields = [
            "id", "username", "full_name", "email", "phone",
            "county", "constituency", "ward",
            "is_verified", "credit_score",
            "id_verified", "gigs", "logged_gigs"
        ]

    def get_gigs(self, obj):
        gigs = Gig.objects.filter(worker=obj)
        return GigSerializer(gigs, many=True).data

    def get_gig_history(self, obj):
        history = GigHistory.objects.filter(worker=obj)  
        return GigHistorySerializer(history, many=True).data  
    


class MpesaNewTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MpesaNewTransaction
        fields = '__all__'


class UserSerializer(serializers.ModelSerializer):
    id_verified = serializers.SerializerMethodField(help_text="Identity documents approved by staff.")

    def get_id_verified(self, obj):
        return _id_verified(obj)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'full_name', 'email', 'phone', 'account_type', 'county', 'constituency', 'ward', 'national_id', 'profile_pic', 'is_verified', 'id_verified',
        ]

class VerificationRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationRequest
        fields = [
            "id", "user", "status",
            "id_front", "id_back", "selfie",
            "rejection_reason", "created_at", "updated_at"
        ]
        read_only_fields = ["user", "status", "created_at", "updated_at", "rejection_reason"]

    def to_representation(self, instance):
        # ID documents are private: hand out short-lived signed links only.
        from .media import signed_media_url
        data = super().to_representation(instance)
        request = self.context.get("request")
        for field in ("id_front", "id_back", "selfie"):
            data[field] = signed_media_url(getattr(instance, field), request)
        return data


class GigsAvailableSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_phone = serializers.CharField(source="organization.phone_number", read_only=True, default=None)

    class Meta:
        model = GigsAvailable
        fields = ['id', 'title', 'description', 'county', 'constituency', 'ward', 'created_at', 'organization',
                  'organization_name', 'organization_phone', 'worker', 'applications_count', 'my_application',
                  'positions', 'is_open', 'filled', 'site_rating', 'saved']
        read_only_fields = ['id', 'created_at', 'organization', 'worker', 'is_open']

    filled = serializers.SerializerMethodField()
    site_rating = serializers.SerializerMethodField()
    saved = serializers.SerializerMethodField()

    def get_filled(self, obj):
        return obj.applications.filter(status="accepted").count()

    def get_site_rating(self, obj):
        from django.db.models import Avg, Count
        agg = obj.organization.site_ratings.aggregate(avg=Avg("stars"), n=Count("id"))
        return {"avg": round(agg["avg"], 1), "count": agg["n"]} if agg["n"] else None

    def get_saved(self, obj):
        req = self.context.get("request")
        return bool(req and req.user.is_authenticated and obj.saved_by.filter(user=req.user).exists())

    def validate_positions(self, v):
        if not 1 <= v <= 50:
            raise serializers.ValidationError("Between 1 and 50.")
        return v

    applications_count = serializers.SerializerMethodField()
    my_application = serializers.SerializerMethodField()

    def get_applications_count(self, obj):
        return obj.applications.filter(status="pending").count()

    def get_my_application(self, obj):
        req = self.context.get("request")
        if not req or not req.user.is_authenticated:
            return None
        a = obj.applications.filter(worker=req.user).first()
        return {"id": a.id, "status": a.status} if a else None


# ########################################
#########################################
##########  REPORTS SERIALIZERS ##########
#########################################
#########################################   


# 1. Weekly Worker Report
class WeeklyWorkerReportSerializer(serializers.Serializer):
    week = serializers.CharField()
    total_workers = serializers.IntegerField()
    verified_workers = serializers.IntegerField()
    unverified_workers = serializers.IntegerField()


# 2. Weekly Gigs Report
class WeeklyGigReportSerializer(serializers.Serializer):
    week = serializers.CharField()
    total_gigs = serializers.IntegerField()
    verified = serializers.IntegerField()
    unverified = serializers.IntegerField()


# 3. Job Type Distribution Report
class JobTypeDistributionSerializer(serializers.Serializer):
    week = serializers.CharField()
    job_type = serializers.CharField()
    count = serializers.IntegerField()


# 4. Organization Performance Report
class OrgPerformanceSerializer(serializers.Serializer):
    organization = serializers.CharField()
    total_gigs = serializers.IntegerField()
    verified = serializers.IntegerField()


# 5. Verification Impact Report
class VerificationImpactSerializer(serializers.Serializer):
    verified_workers_count = serializers.IntegerField()
    verified_avg_gigs = serializers.FloatField()
    unverified_workers_count = serializers.IntegerField()
    unverified_avg_gigs = serializers.FloatField()



##############################################################
##############################################################
##########  SINGLE USER GIGS AND HISTORY SERIALIZERS ##########
##############################################################
##############################################################

class GigCountSerializer(serializers.Serializer):
    period = serializers.CharField()
    total_gigs = serializers.IntegerField()

class GigCompletionRateSerializer(serializers.Serializer):
    total_gigs = serializers.IntegerField()
    completed_gigs = serializers.IntegerField()
    completion_rate = serializers.FloatField()

class GigRevenueSerializer(serializers.Serializer):
    period = serializers.CharField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)

class GigTrendsSerializer(serializers.Serializer):
    week = serializers.CharField()
    completed_gigs = serializers.IntegerField()

class TopGigsSerializer(serializers.Serializer):
    gig_title = serializers.CharField()
    revenue = serializers.DecimalField(max_digits=12, decimal_places=2)



# dashbaord api fundipro

class DashboardGigSerializer(serializers.ModelSerializer):
    """
    Simplified Gig serializer for dashboard display
    """
    job_type_name = serializers.CharField(source='job_type.name', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)
    verified_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Gig
        fields = [
            'id', 'job_type_name', 'organization_name', 'start_date',
            'duration_value', 'duration_unit', 'is_verified', 'verified_by_name',
            'amount_paid', 'created_at', 'is_complete'
        ]
    
    def get_verified_by_name(self, obj):
        if obj.verified_by:
            return obj.verified_by.full_name or obj.verified_by.username
        return None


class DashboardStatsSerializer(serializers.Serializer):
    """
    Serializer for dashboard statistics response
    """
    total_gigs = serializers.IntegerField()
    verified_gigs = serializers.IntegerField()
    verified_days = serializers.IntegerField()
    verification_rate = serializers.FloatField()
    sites_worked = serializers.IntegerField()
    disputes = serializers.IntegerField()
    history_months = serializers.IntegerField()
    credit_score = serializers.IntegerField()


class WorkLogSerializer(serializers.Serializer):
    """
    Serializer for work log display in dashboard
    """
    id = serializers.IntegerField()
    siteName = serializers.CharField()
    jobType = serializers.CharField()
    date = serializers.DateField()
    verified = serializers.BooleanField()
    foremanName = serializers.CharField(required=False, allow_null=True)


class CalendarDaySerializer(serializers.Serializer):
    """
    Serializer for calendar day display
    """
    date = serializers.DateField()
    dayNum = serializers.IntegerField()
    status = serializers.ChoiceField(choices=['verified', 'pending', 'empty'])
    tooltip = serializers.CharField()


class GigSearchResultSerializer(serializers.ModelSerializer):
    """Gig as shown to people who are not its worker or its site's contractor."""

    job_type_name = serializers.CharField(source="job_type.name", read_only=True, default=None)
    organization_name = serializers.CharField(source="organization.name", read_only=True, default=None)
    worker_name = serializers.SerializerMethodField()

    def get_worker_name(self, obj):
        w = obj.worker
        return (w.full_name or w.username) if w else None

    worker_username = serializers.CharField(source="worker.username", read_only=True, default=None)

    class Meta:
        model = Gig
        exclude = ['client_phone', 'amount_paid', 'logged_by', 'verified_by']
