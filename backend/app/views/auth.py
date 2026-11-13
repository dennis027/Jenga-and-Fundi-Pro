"""Accounts: registration, activation, login/logout, password reset, profile."""
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


class CheckEmailExists(APIView):
    permission_classes = [AllowAny] 
    def get(self, request):
        email = request.query_params.get('email')
        if not email:
            return Response({"error": "Email parameter is required"}, status=400)
        
        if User.objects.filter(email__iexact=email).exists():
            return Response({"exists": True, "message": "Email already exists"}, status=200)
        return Response({"exists": False, "message": "Email is available"}, status=400)


class CheckUsernameExists(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        username = request.query_params.get('username')
        if not username:
            return Response({"error": "Username parameter is required"}, status=400)
        
        if User.objects.filter(username__iexact=username).exists():
            return Response({"exists": True, "message": "Username already exists"}, status=200)
        return Response({"exists": False, "message": "Username is available"}, status=400)

class UserListAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]  # every user's personal data

    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


class CheckPhoneExists(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        phone = request.query_params.get('phone')
        if not phone:
            return Response({"error": "Phone parameter is required"}, status=400)
        
        if User.objects.filter(phone__iexact=phone).exists():
            return Response({"exists": True, "message": "Phone number already exists"}, status=200)
        return Response({"exists": False, "message": "Phone number is available"}, status=400)

class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get('email', '').lower()
        username = request.data.get('username', '')

        # Check if user exists
        existing_user = User.objects.filter(email__iexact=email).first()
        if existing_user:
            if not existing_user.is_verified:
                return Response({
                    "code": "EMAIL_NOT_VERIFIED",
                    "message": "Account exists but not verified. Please check your email.",
                    "email": existing_user.email
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    "message": "Email already registered."
                }, status=status.HTTP_400_BAD_REQUEST)

        existing_username = User.objects.filter(username__iexact=username).first()
        if existing_username:
            return Response({
                "message": "Username already in use."
            }, status=status.HTTP_400_BAD_REQUEST)

        # Proceed with registration
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate activation link
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        activation_link = request.build_absolute_uri(
            reverse('activate', kwargs={'uidb64': uidb64, 'token': token})
        )

        subject = "Activate Your Account"
        html_content = render_to_string('activation/activation_email.html', {
            'username': user.username,
            'activation_link': activation_link
        })

        try:
            send_mail_async(subject, '', settings.DEFAULT_FROM_EMAIL, [user.email], html_message=html_content)
        except Exception as e:
            return Response({"error": f"Failed to send activation email: {str(e)}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "message": "Registration successful. Please check your email to activate your account."
        }, status=status.HTTP_201_CREATED)


class ActivateAccountAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        try:
            user_id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return Response({"error": "Invalid link"}, status=400)

        if default_token_generator.check_token(user, token):
            user.is_verified = True
            user.save()
            # return Response({"message": "Account activated successfully"})
            request.session['activation_done'] = True 
            return redirect('/activation-success/')
        else:
            # return Response({"error": "Invalid or expired token"}, status=400)
            request.session['activation_done'] = True 
            return redirect('/activation-failed/')
        
        
class ResendVerificationEmailView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"message": "If the email exists, a verification link has been sent."},
                status=status.HTTP_200_OK
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"message": "If the email exists, a verification link has been sent."},
                status=status.HTTP_200_OK
            )

        if user.is_verified: 
            return Response(
                {"message": "If the email exists, a verification link has been sent."},
                status=status.HTTP_200_OK
            )

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        activation_link = request.build_absolute_uri(
            reverse('activate', kwargs={'uidb64': uidb64, 'token': token})
        )

        html_content = render_to_string('activation/activation_email.html', {
            'username': user.username,
            'activation_link': activation_link
        })

        send_mail_async(
            subject="Activate Your Account",
            message="",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_content
        )

        return Response(
            {"message": "If the email exists, a verification link has been sent."},
            status=status.HTTP_200_OK
        )




def activation_success_view(request):
    if request.session.pop('activation_done', None):  # remove flag after use
        return render(request, 'activation/activation_success.html')
    return redirect('/')  # or 404 page


def activation_failed_view(request):
    if request.session.pop('activation_done', None):
        return render(request, 'activation/activation_failed.html')
    return redirect('/')




class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        login_input = serializer.validated_data['username']
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(
                Q(username__iexact=login_input) |
                Q(email__iexact=login_input) |
                Q(phone__iexact=login_input)
            )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Check if user is verified
        if not user.is_verified:
            return Response(
                {
                    "code": "EMAIL_NOT_VERIFIED",
                    "message": "Account exists but not verified. Please check your email.",
                    "email": user.email
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = authenticate(
            request=request,
            username=user.username,
            password=password
        )

        if not user:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "account_type": user.account_type
            }
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data['refresh']
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Logged out successfully"}, status=status.HTTP_205_RESET_CONTENT)
        except TokenError:
            return Response({"detail": "Invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        

# password reset code generation
class RequestPasswordResetView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({"error": "Email is required"}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if user exists (security)
            return Response({"message": "If this email exists, a reset code has been sent."})

        # Generate a 6-digit code
        code = f"{secrets.randbelow(1_000_000):06d}"
        PasswordResetCode.objects.create(user=user, code=code)

        # Send beautiful email with the code
        try:
            self.send_password_reset_email(user, code)
        except Exception as e:
            logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
            # Still return success message for security
            return Response({"message": "If this email exists, a reset code has been sent."})

        return Response({"message": "If this email exists, a reset code has been sent."})

    def send_password_reset_email(self, user, code):
        """
        Send a beautifully designed password reset email
        """
        subject = "Your Password Reset Code"
        
        # Get current time for display
        current_time = timezone.now().strftime('%B %d, %Y at %I:%M %p')
        
        # HTML email template with modern, beautiful design
        html_message = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Password Reset Code</title>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                    line-height: 1.6;
                    color: #2c3e50;
                    background-color: #f8fafc;
                }}
                
                .email-container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                    border-radius: 12px;
                    overflow: hidden;
                }}
                
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 40px 30px;
                    text-align: center;
                    position: relative;
                }}
                
                .header::before {{
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    bottom: 0;
                    background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="rgba(255,255,255,0.1)"/><circle cx="75" cy="75" r="1" fill="rgba(255,255,255,0.1)"/><circle cx="25" cy="75" r="1" fill="rgba(255,255,255,0.05)"/><circle cx="75" cy="25" r="1" fill="rgba(255,255,255,0.05)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
                    opacity: 0.3;
                }}
                
                .header-content {{
                    position: relative;
                    z-index: 1;
                }}
                
                .lock-icon {{
                    width: 60px;
                    height: 60px;
                    margin: 0 auto 20px;
                    background: rgba(255, 255, 255, 0.2);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    backdrop-filter: blur(10px);
                }}
                
                .header h1 {{
                    color: #ffffff;
                    font-size: 28px;
                    font-weight: 600;
                    margin-bottom: 8px;
                }}
                
                .header p {{
                    color: rgba(255, 255, 255, 0.9);
                    font-size: 16px;
                }}
                
                .content {{
                    padding: 40px 30px;
                }}
                
                .greeting {{
                    font-size: 18px;
                    color: #2c3e50;
                    margin-bottom: 25px;
                }}
                
                .code-section {{
                    text-align: center;
                    margin: 30px 0;
                    padding: 30px 20px;
                    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
                    border-radius: 12px;
                    position: relative;
                    overflow: hidden;
                }}
                
                .code-section::before {{
                    content: '';
                    position: absolute;
                    top: -50%;
                    left: -50%;
                    width: 200%;
                    height: 200%;
                    background: repeating-conic-gradient(rgba(255,255,255,0.1) 0deg, rgba(255,255,255,0.1) 2deg, transparent 2deg, transparent 4deg);
                    animation: rotate 20s linear infinite;
                }}
                
                @keyframes rotate {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
                
                .code-label {{
                    color: rgba(255, 255, 255, 0.9);
                    font-size: 14px;
                    font-weight: 500;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                    margin-bottom: 15px;
                    position: relative;
                    z-index: 1;
                }}
                
                .code {{
                    font-size: 36px;
                    font-weight: 700;
                    color: #ffffff;
                    letter-spacing: 8px;
                    font-family: 'Courier New', monospace;
                    text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
                    position: relative;
                    z-index: 1;
                    margin-bottom: 10px;
                }}
                
                .code-note {{
                    color: rgba(255, 255, 255, 0.9);
                    font-size: 14px;
                    position: relative;
                    z-index: 1;
                }}
                
                .instructions {{
                    background: #f8fafc;
                    border-left: 4px solid #3b82f6;
                    padding: 20px;
                    margin: 25px 0;
                    border-radius: 0 8px 8px 0;
                }}
                
                .instructions h3 {{
                    color: #1e40af;
                    font-size: 16px;
                    margin-bottom: 10px;
                    display: flex;
                    align-items: center;
                }}
                
                .instructions ol {{
                    margin-left: 20px;
                    color: #4b5563;
                }}
                
                .instructions li {{
                    margin-bottom: 8px;
                }}
                
                .security-notice {{
                    background: #fef3c7;
                    border: 1px solid #f59e0b;
                    color: #92400e;
                    padding: 20px;
                    border-radius: 8px;
                    margin: 25px 0;
                }}
                
                .security-notice h4 {{
                    font-size: 16px;
                    margin-bottom: 10px;
                    display: flex;
                    align-items: center;
                }}
                
                .timer-box {{
                    background: #fee2e2;
                    border: 1px solid #fca5a5;
                    color: #dc2626;
                    padding: 15px;
                    border-radius: 8px;
                    text-align: center;
                    margin: 20px 0;
                    font-weight: 500;
                }}
                
                .footer {{
                    background: #f9fafb;
                    padding: 30px;
                    text-align: center;
                    color: #6b7280;
                    font-size: 14px;
                    border-top: 1px solid #e5e7eb;
                }}
                
                .footer p {{
                    margin-bottom: 8px;
                }}
                
                .company-name {{
                    color: #374151;
                    font-weight: 600;
                }}
                
                .divider {{
                    height: 1px;
                    background: linear-gradient(90deg, transparent, #e5e7eb, transparent);
                    margin: 20px 0;
                }}
                
                @media (max-width: 600px) {{
                    .email-container {{
                        margin: 10px;
                        border-radius: 8px;
                    }}
                    
                    .header, .content {{
                        padding: 30px 20px;
                    }}
                    
                    .code {{
                        font-size: 30px;
                        letter-spacing: 6px;
                    }}
                }}
            </style>
        </head>
        <body>
            <div class="email-container">
                <div class="header">
                    <div class="header-content">
                        <div class="lock-icon">
                            <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" style="color: white;">
                                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                                <circle cx="12" cy="16" r="1"></circle>
                                <path d="m12 13v4"></path>
                                <path d="M8 11V7a4 4 0 0 1 8 0v4"></path>
                            </svg>
                        </div>
                        <h1>Password Reset</h1>
                        <p>Secure access to your account</p>
                    </div>
                </div>
                
                <div class="content">
                    <div class="greeting">
                        Hello {user.first_name or 'there'} 👋
                    </div>
                    
                    <p style="margin-bottom: 25px; color: #4b5563; font-size: 16px;">
                        We received a request to reset the password for your account associated with <strong>{user.email}</strong>.
                    </p>
                    
                    <div class="code-section">
                        <div class="code-label">Your Reset Code</div>
                        <div class="code">{code}</div>
                        <div class="code-note">Enter this code to reset your password</div>
                    </div>
                    
                    <div class="timer-box">
                        ⏰ This code will expire in <strong>30 minutes</strong>
                    </div>
                    
                    <div class="instructions">
                        <h3>
                            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" style="margin-right: 8px;">
                                <circle cx="12" cy="12" r="10"></circle>
                                <path d="M12 16v-4"></path>
                                <path d="M12 8h.01"></path>
                            </svg>
                            How to use this code:
                        </h3>
                        <ol>
                            <li>Return to the password reset page</li>
                            <li>Enter the 6-digit code above</li>
                            <li>Create your new secure password</li>
                            <li>Confirm your new password</li>
                        </ol>
                    </div>
                    
                    <div class="security-notice">
                        <h4>
                            <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2" style="margin-right: 8px;">
                                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                                <line x1="12" y1="9" x2="12" y2="13"></line>
                                <line x1="12" y1="17" x2="12.01" y2="17"></line>
                            </svg>
                            Security Notice
                        </h4>
                        <p>If you didn't request this password reset, please ignore this email or contact our support team if you have concerns about your account security.</p>
                    </div>
                    
                    <div class="divider"></div>
                    
                    <p style="color: #6b7280; font-size: 14px; text-align: center;">
                        Need help? Contact our support team or visit our help center.
                    </p>
                </div>
                
                <div class="footer">
                    <p><span class="company-name">{getattr(settings, 'SITE_NAME', 'Your App')}</span></p>
                    <p>This email was sent on {current_time}</p>
                    <p>This is an automated message, please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version for email clients that don't support HTML
        plain_message = f"""
        Password Reset Code

        Hello {user.first_name or 'there'},

        We received a request to reset the password for your account: {user.email}

        Your reset code is: {code}

        This code will expire in 30 minutes.

        How to use this code:
        1. Return to the password reset page
        2. Enter the 6-digit code above
        3. Create your new secure password
        4. Confirm your new password

        SECURITY NOTICE:
        If you didn't request this password reset, please ignore this email or contact our support team.

        This email was sent on {current_time}
        This is an automated message, please do not reply.

        {getattr(settings, 'SITE_NAME', 'Your App')}
        """

        try:
            send_mail_async(
                subject=subject,
                message=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Password reset email sent successfully to {user.email}")
            
        except Exception as e:
            logger.error(f"Failed to send password reset email: {str(e)}")
            raise
    
@ensure_csrf_cookie
@require_http_methods(["GET"])
def csrf_token_view(request):
    return JsonResponse({'csrf_token': get_token(request)})
    
@method_decorator(csrf_exempt, name='dispatch')
class VerifyResetCodeView(APIView):
    authentication_classes = []  # Disable DRF authentication
    permission_classes = []      # Disable DRF permissions
    
    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')

        if not email or not code:
            return Response({"error": "Email and code are required"}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid email or code"}, status=400)

        try:
            reset_code = PasswordResetCode.objects.filter(
                user=user, code=code
            ).latest('created_at')
        except PasswordResetCode.DoesNotExist:
            return Response({"error": "Invalid code"}, status=400)

        if reset_code.is_expired():
            return Response({"error": "Code expired"}, status=400)

        return Response({"message": "Code is valid"}, status=200)


class ConfirmResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        code = request.data.get('code')
        new_password = request.data.get('new_password')
        reset_password = request.data.get('reset_password')  # confirm password

        # Check all required fields
        if not all([email, code, new_password, reset_password]):
            return Response({"error": "Email, code, new_password, and reset_password are required"}, status=400)

        # Check if passwords match
        if new_password != reset_password:
            return Response({"error": "Passwords do not match"}, status=400)

        # Check if user exists
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Invalid email or code"}, status=400)

        # Check if code exists
        try:
            reset_code = PasswordResetCode.objects.filter(user=user, code=code).latest('created_at')
        except PasswordResetCode.DoesNotExist:
            return Response({"error": "Invalid code"}, status=400)

        # Check if code expired
        if reset_code.is_expired():
            return Response({"error": "Code expired"}, status=400)

        # Reset password
        user.set_password(new_password)
        user.save()

        # Remove the code after successful reset
        reset_code.delete()

        # Send confirmation email
        try:
            self.send_password_reset_confirmation_email(user)
        except Exception as e:
            logger.error(f"Failed to send password reset confirmation email to {user.email}: {str(e)}")
            # Don't fail the request if email sending fails

        return Response({"message": "Password reset successful"})

    def send_password_reset_confirmation_email(self, user):
        """
        Send a confirmation email after successful password reset
        """
        subject = "Password Reset Successful"
        
        # HTML email template
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Password Reset Confirmation</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f9f9f9; }}
                .footer {{ padding: 20px; text-align: center; color: #666; font-size: 14px; }}
                .alert {{ background-color: #fff3cd; border: 1px solid #ffeeba; color: #856404; padding: 15px; margin: 15px 0; border-radius: 4px; }}
                .btn {{ display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 4px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset Successful</h1>
                </div>
                
                <div class="content">
                    <h2>Hello {user.first_name or 'User'},</h2>
                    
                    <p>Your password has been successfully reset for the account associated with <strong>{user.email}</strong>.</p>
                    
                    <p><strong>Reset Details:</strong></p>
                    <ul>
                        <li>Date: {user.last_login.strftime('%B %d, %Y at %I:%M %p') if user.last_login else 'Just now'}</li>
                        <li>Account: {user.email}</li>
                    </ul>
                    
                    <div class="alert">
                        <strong>⚠️ Important Security Notice:</strong><br>
                        If you did not request this password reset, please take the following actions immediately:
                        <ol>
                            <li>Change your password again by logging into your account</li>
                            <li>Review your account security settings</li>
                            <li>Contact our support team if you suspect unauthorized access</li>
                        </ol>
                    </div>
                    
                    <p>If you made this change, no further action is required. You can now log in with your new password.</p>
                    
                    <p><strong>Security Tips:</strong></p>
                    <ul>
                        <li>Use a strong, unique password</li>
                        <li>Enable two-factor authentication if available</li>
                        <li>Never share your login credentials</li>
                        <li>Log out of shared or public computers</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>This email was sent from an automated system. Please do not reply to this email.</p>
                    <p>If you have any questions, please contact our support team.</p>
                    <p>&copy; {settings.SITE_NAME if hasattr(settings, 'SITE_NAME') else 'Your App'} - All rights reserved</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version for email clients that don't support HTML
        plain_message = f"""
        Password Reset Successful

        Hello {user.first_name or 'User'},

        Your password has been successfully reset for the account associated with {user.email}.

        IMPORTANT SECURITY NOTICE:
        If you did not request this password reset, please:
        1. Change your password again immediately
        2. Review your account security settings  
        3. Contact our support team if you suspect unauthorized access

        If you made this change, no further action is required. You can now log in with your new password.

        Security Tips:
        - Use a strong, unique password
        - Enable two-factor authentication if available
        - Never share your login credentials
        - Log out of shared or public computers

        This email was sent from an automated system. Please do not reply to this email.
        If you have any questions, please contact our support team.
        """

        try:
            send_mail_async(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )
            logger.info(f"Password reset confirmation email sent successfully to {user.email}")
            
        except Exception as e:
            logger.error(f"Failed to send password reset confirmation email: {str(e)}")
            raise

    def get_support_email(self):
        """
        Get support email from settings or return default
        """
        return getattr(settings, 'SUPPORT_EMAIL', 'support@yourapp.com')



class CookieLoginView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = authenticate(
                username=serializer.validated_data['username'],
                password=serializer.validated_data['password']
            )
            if user:
                refresh = RefreshToken.for_user(user)
                response = Response({
                    'message': 'Login successful',
                })

                access_token_expiry = now() + timedelta(minutes=15)
                refresh_token_expiry = now() + timedelta(days=7)

                response.set_cookie(
                    key='access_token',
                    value=str(refresh.access_token),
                    httponly=True,
                    expires=access_token_expiry,
                    samesite='Lax',
                    secure=False  # Change to True in production (HTTPS)
                )
                response.set_cookie(
                    key='refresh_token',
                    value=str(refresh),
                    httponly=True,
                    expires=refresh_token_expiry,
                    samesite='Lax',
                    secure=False
                )
                return response
            return Response({"error": "Invalid credentials"}, status=401)
        return Response(serializer.errors, status=400)
    

class ProfileUpdateView(APIView):
    authentication_classes = [JWTAuthentication]   
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def put(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Profile updated successfully'})
        return Response(serializer.errors, status=400)

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
