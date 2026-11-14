"""M-Pesa STK push/callback, transaction history, payment screenshots and OCR."""
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
from ..models import CreditScoreHistory, Gig, Payment, GigsAvailable,JobType,GigHistory, Organization,MpesaNewTransaction,UserPaymentSession,PhoneOTP, VerificationRequest
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


def mpesa_callback_url():
    """Callback URL sent to Safaricom, carrying the shared secret when configured."""
    if not settings.MPESA_CALLBACK_TOKEN:
        return CALLBACK_URL
    sep = "&" if "?" in CALLBACK_URL else "?"
    return f"{CALLBACK_URL}{sep}token={settings.MPESA_CALLBACK_TOKEN}"


class PaymentUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # allow both

    def get(self, request):
        payments = Payment.objects.filter(user=request.user).order_by("-payment_date")
        return Response(PaymentSerializer(payments, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = PaymentSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)  


@csrf_exempt
def extract_transaction_code(request):
    if request.method == 'POST' and request.FILES.get('image'):
        uploaded_image = request.FILES['image']
        # Read straight from the upload: works with any storage backend and never
        # writes the payment screenshot to disk.
        image = Image.open(uploaded_image)
        text = pytesseract.image_to_string(image)

        # Clean and normalize text
        clean_text = text.strip().replace('\n', ' ').replace('\r', ' ')
        clean_text = ' '.join(clean_text.split())  # Remove extra whitespace
        text_lower = clean_text.lower()
        
        # Check if it's a valid M-Pesa message
        mpesa_indicators = ['confirmed', 'ksh', 'sent to', 'received from', 'mpesa']
        found_indicators = sum(1 for indicator in mpesa_indicators if indicator in text_lower)
        is_valid_mpesa = found_indicators >= 3
        
        # Check for message completeness
        completeness_indicators = ['confirmed', 'ksh', 'transaction cost', 'account balance']
        completeness_score = sum(1 for indicator in completeness_indicators if indicator in text_lower)
        is_complete = completeness_score >= 3 or ('sent to' in text_lower or 'received from' in text_lower)
        
        # Extract transaction code - multiple patterns
        transaction_code = None
        
        # Pattern 1: Code before "Confirmed"
        match = re.search(r'\b([A-Z0-9]{8,12})\b(?=\s+[Cc]onfirmed)', clean_text)
        if match:
            transaction_code = match.group(1)
        else:
            # Pattern 2: Code after "Confirmed"
            match = re.search(r'[Cc]onfirmed\.?\s+([A-Z0-9]{8,12})', clean_text)
            if match:
                transaction_code = match.group(1)
            else:
                # Pattern 3: General M-Pesa code format
                codes = re.findall(r'\b([A-Z]{2}[0-9]{8}|[A-Z0-9]{10})\b', clean_text)
                false_positives = ['MPESA', 'SAFARICOM', 'CONFIRMED']
                valid_codes = [code for code in codes if code not in false_positives and len(code) >= 8]
                if valid_codes:
                    transaction_code = valid_codes[0]
        
        # Extract amount - multiple patterns
        amount = None
        
        # Pattern 1: Amount before "sent to" or "received from"
        match = re.search(r'[Kk][Ss][Hh]\.?\s*([0-9,]+\.?[0-9]*)\s+(?:sent\s+to|received\s+from)', clean_text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '').strip()
            try:
                amount = float(amount_str)
            except ValueError:
                pass
        
        if not amount:
            # Pattern 2: Amount after "Confirmed"
            match = re.search(r'[Cc]onfirmed\.?\s+[Kk][Ss][Hh]\.?\s*([0-9,]+\.?[0-9]*)', clean_text)
            if match:
                amount_str = match.group(1).replace(',', '').strip()
                try:
                    amount = float(amount_str)
                except ValueError:
                    pass
        
        if not amount:
            # Pattern 3: Any KSH amount (take the largest one)
            amounts = re.findall(r'[Kk][Ss][Hh]\.?\s*([0-9,]+\.?[0-9]*)', clean_text)
            if amounts:
                valid_amounts = []
                for amt in amounts:
                    try:
                        clean_amt = float(amt.replace(',', '').strip())
                        if clean_amt > 0:
                            valid_amounts.append(clean_amt)
                    except ValueError:
                        continue
                if valid_amounts:
                    amount = max(valid_amounts)  # Take the largest amount (likely the transaction amount)

        return JsonResponse({
            'text': text,
            'transaction_code': transaction_code,
            'amount': amount,
            'is_valid_mpesa': is_valid_mpesa,
            'is_complete_message': is_complete
        })

    return JsonResponse({'error': 'Image not provided'}, status=400)




############################################################
############################################################
#######  M-PESA STK Push and Callback Views ################
############################################################
############################################################
def generate_password():
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    data = BUSINESS_SHORTCODE + PASSKEY + timestamp
    password = base64.b64encode(data.encode()).decode()
    return password, timestamp

MPESA_TOKEN_CACHE_KEY = "mpesa:access_token"

def get_access_token():
    """Return a Daraja OAuth token, cached in Redis until shortly before expiry.

    Falls back to a direct request if the cache is unavailable.
    """
    try:
        token = cache.get(MPESA_TOKEN_CACHE_KEY)
    except Exception:
        logger.warning("Cache unavailable; requesting M-Pesa token directly", exc_info=True)
        token = None
    if token:
        return token

    response = requests.get(
        f"{settings.MPESA_BASE_URL}/oauth/v1/generate?grant_type=client_credentials",
        auth=(CONSUMER_KEY, CONSUMER_SECRET),
        timeout=30,
    )
    data = response.json()
    token = data.get('access_token')
    if token:
        ttl = max(int(data.get('expires_in', 3599)) - 60, 60)
        try:
            cache.set(MPESA_TOKEN_CACHE_KEY, token, ttl)
        except Exception:
            logger.warning("Could not cache M-Pesa token", exc_info=True)
    return token

class STKNewPushView(APIView):
    permission_classes = [IsAuthenticated]  # Add authentication requirement
    
    def post(self, request):
        phone = request.data.get("phone_number")
        amount = request.data.get("amount")

        password, timestamp = generate_password()
        access_token = get_access_token()

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "BusinessShortCode": BUSINESS_SHORTCODE,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": BUSINESS_SHORTCODE,
            "PhoneNumber": phone,
            "CallBackURL": mpesa_callback_url(),
            "AccountReference": settings.MPESA_ACCOUNT_REFERENCE,
            "TransactionDesc": "Payment"
        }

        response = requests.post(
            f"{settings.MPESA_BASE_URL}/mpesa/stkpush/v1/processrequest",
            json=payload, headers=headers
        )
        
        # Save user session after successful STK push
        if response.status_code == 200:
            response_data = response.json()
            checkout_request_id = response_data.get('CheckoutRequestID')
            merchant_request_id = response_data.get('MerchantRequestID')
            
            # Save user session
            try:
                UserPaymentSession.objects.create(
                    user=request.user,
                    phone_number=phone,
                    checkout_request_id=checkout_request_id,
                    merchant_request_id=merchant_request_id,
                    amount=amount,
                )

                logger.info(f"✅ User session saved for {request.user.username}")
            except Exception as e:
                logger.error(f"❌ Failed to save user session: {str(e)}")
        
        return Response(response.json())


@method_decorator(csrf_exempt, name='dispatch')
class STKNewCallbackView(APIView):
    """Safaricom STK callback.

    Only accepted when the URL carries MPESA_CALLBACK_TOKEN (if configured) and the
    CheckoutRequestID belongs to a push this app started. Each checkout is recorded
    once; the paid amount must match the requested amount.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = settings.MPESA_CALLBACK_TOKEN
        if token and not constant_time_compare(request.query_params.get("token", ""), token):
            logger.warning("Rejected M-Pesa callback with a missing/invalid token")
            return Response({"ResultCode": 1, "ResultDesc": "Rejected"}, status=status.HTTP_403_FORBIDDEN)

        callback = (request.data or {}).get('Body', {}).get('stkCallback', {})
        result_code = callback.get('ResultCode')
        result_desc = callback.get('ResultDesc')
        merchant_request_id = callback.get('MerchantRequestID')
        checkout_request_id = callback.get('CheckoutRequestID')
        logger.info("M-Pesa callback: checkout=%s result=%s", checkout_request_id, result_code)

        session = UserPaymentSession.objects.filter(checkout_request_id=checkout_request_id).select_related("user").first()
        if not session:
            logger.warning("Ignored M-Pesa callback for unknown checkout %s", checkout_request_id)
            return Response({"ResultCode": 0, "ResultDesc": "Ignored"})

        existing = MpesaNewTransaction.objects.filter(checkout_request_id=checkout_request_id).first()
        if existing:
            return Response({"status": "duplicate", "transaction": existing.mpesa_receipt_number})

        if result_code == 0:
            items = callback.get('CallbackMetadata', {}).get('Item', [])
            item_map = {item.get('Name'): item.get('Value') for item in items}
            amount = item_map.get('Amount')
            if session.amount is not None and amount is not None and float(amount) != float(session.amount):
                logger.error("M-Pesa amount mismatch for %s: requested %s, callback %s",
                             checkout_request_id, session.amount, amount)
                return Response({"ResultCode": 1, "ResultDesc": "Amount mismatch"}, status=status.HTTP_400_BAD_REQUEST)

            txn = MpesaNewTransaction.objects.create(
                user=session.user,
                phone_number=item_map.get('PhoneNumber'),
                amount=amount,
                mpesa_receipt_number=item_map.get('MpesaReceiptNumber'),
                transaction_date=datetime.strptime(str(item_map.get('TransactionDate')), "%Y%m%d%H%M%S"),
                merchant_request_id=merchant_request_id,
                checkout_request_id=checkout_request_id,
                result_code=result_code,
                result_desc=result_desc,
                raw_callback=callback,
            )
            return Response({"status": "success", "transaction": txn.mpesa_receipt_number})

        MpesaNewTransaction.objects.create(
            user=session.user,
            phone_number=session.phone_number or "Unknown",
            amount=0,
            # receipt is unique: derive a per-checkout placeholder for failed payments
            mpesa_receipt_number=("F-" + (checkout_request_id or "unknown"))[-20:],
            transaction_date=timezone.now(),
            merchant_request_id=merchant_request_id,
            checkout_request_id=checkout_request_id,
            result_code=result_code,
            result_desc=result_desc,
            raw_callback=callback,
        )
        return Response({"status": "failed", "reason": result_desc})


class MpesaMessagesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        transactions = MpesaNewTransaction.objects.all()
        if not request.user.is_staff:
            transactions = transactions.filter(user=request.user)

        # Optional filters
        phone_number = request.query_params.get('phone_number')
        amount = request.query_params.get('amount')
        receipt = request.query_params.get('mpesa_receipt_number')
        date_from = request.query_params.get('date_from')  # format: YYYY-MM-DD
        date_to = request.query_params.get('date_to')      # format: YYYY-MM-DD
        user_id = request.query_params.get('user_id')      # filter by specific user (optional)

        if phone_number:
            transactions = transactions.filter(phone_number=phone_number)
        if amount:
            transactions = transactions.filter(amount=amount)
        if receipt:
            transactions = transactions.filter(mpesa_receipt_number=receipt)
        if date_from:
            transactions = transactions.filter(transaction_date__gte=date_from)
        if date_to:
            transactions = transactions.filter(transaction_date__lte=date_to)
        if user_id:
            transactions = transactions.filter(user__id=user_id)

        transactions = transactions.order_by('-transaction_date')
        serializer = MpesaNewTransactionSerializer(transactions, many=True)

        return Response({
            "count": transactions.count(),
            "transactions": serializer.data
        }, status=status.HTTP_200_OK)
    




class UserMpesaMessagesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        transactions = MpesaNewTransaction.objects.filter(user=request.user)

        # Optional filters
        phone_number = request.query_params.get('phone_number')
        amount = request.query_params.get('amount')
        receipt = request.query_params.get('mpesa_receipt_number')
        date_from = request.query_params.get('date_from')  # format: YYYY-MM-DD
        date_to = request.query_params.get('date_to')      # format: YYYY-MM-DD

        if phone_number:
            transactions = transactions.filter(phone_number=phone_number)
        if amount:
            transactions = transactions.filter(amount=amount)
        if receipt:
            transactions = transactions.filter(mpesa_receipt_number=receipt)
        if date_from:
            transactions = transactions.filter(transaction_date__gte=date_from)
        if date_to:
            transactions = transactions.filter(transaction_date__lte=date_to)

        transactions = transactions.order_by('-transaction_date')
        serializer = MpesaNewTransactionSerializer(transactions, many=True)

        return Response({
            "count": transactions.count(),
            "user_id": request.user.id,
            "username": request.user.username,
            "transactions": serializer.data
        }, status=status.HTTP_200_OK)
