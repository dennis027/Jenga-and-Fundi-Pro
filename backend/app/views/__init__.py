"""API views, grouped by area. Re-exported so `from app.views import X` keeps working."""
from .auth import (  # noqa: F401
    ActivateAccountAPIView,
    CheckEmailExists,
    CheckPhoneExists,
    CheckUsernameExists,
    ConfirmResetPasswordView,
    CookieLoginView,
    LoginView,
    LogoutView,
    ProfileUpdateView,
    RegisterView,
    RequestPasswordResetView,
    ResendVerificationEmailView,
    UserListAPIView,
    UserProfileView,
    VerifyResetCodeView,
    activation_failed_view,
    activation_success_view,
    csrf_token_view,
)
from .phone import (  # noqa: F401
    SendOTPView,
    VerifyOTPView,
    _client_ip,

    api_key,
    sms,
    username,
)
from .payments import (  # noqa: F401
    MPESA_TOKEN_CACHE_KEY,
    MpesaMessagesAPIView,
    PaymentUploadView,
    STKNewCallbackView,
    STKNewPushView,
    UserMpesaMessagesAPIView,
    extract_transaction_code,
    generate_password,
    get_access_token,
    mpesa_callback_url,
)
from .verification import (  # noqa: F401
    LatestVerificationView,
    VerificationActionView,
    VerificationRequestCreateView,
    VerificationRequestListView,
)
from .reports import (  # noqa: F401
    GigCompletionRateView,
    GigCountAnalysisView,
    GigRevenueAnalysisView,
    GigTrendsView,
    JobTypeDistributionReportView,
    OrgPerformanceReportView,
    TopEarningGigsView,
    VerificationImpactReportView,
    WeeklyGigReportView,
    WeeklyWorkerReportView,
)
from .fundi_dashboard import (  # noqa: F401
    Fundi30DayCalendarView,
    FundiAllGigsView,
    FundiComparativeAnalyticsView,
    FundiCreditScoreAnalyticsView,
    FundiCreditScoreHistoryView,
    FundiDashboardStatsView,
    FundiEarningsAnalyticsView,
    FundiJobTypeAnalyticsView,
    FundiLocationAnalyticsView,
    FundiOrganizationPerformanceView,
    FundiOrganizationsWorkedView,
    FundiRecentWorkLogsView,
    FundiSummaryDashboardView,
    FundiVerificationMetricsView,
    FundiWorkConsistencyView,
    FundiWorkTrendsView,
)
from .contractor_dashboard import (  # noqa: F401
    Contractor7DayCalendarView,
    ContractorComparativeAnalyticsView,
    ContractorDashboardStatsView,
    ContractorGigTrendsView,
    ContractorGigsByOrganizationView,
    ContractorJobTypeAnalyticsView,
    ContractorLocationAnalyticsView,
    ContractorOrganizationPerformanceView,
    ContractorOrganizationsView,
    ContractorRecentGigsView,
    ContractorRevenueAnalyticsView,
    ContractorSummaryDashboardView,
    ContractorTopSitesView,
    ContractorTopWorkersView,
    ContractorUnverifiedGigsView,
    ContractorVerificationMetricsView,
    ContractorWeeklyChartView,
    ContractorWorkerPerformanceView,
    ContractorWorkerRetentionView,
)
from .gigs import (  # noqa: F401
    CompleteGigAPIView,
    CreditScoreHistoryView,
    GigHistoryView,
    GigListView,
    GigSearchView,
    GigsAvailableListCreateView,
    JobTypeDeleteView,
    JobTypeListCreateView,
    LogGigView,
    LoggedByUserGigListView,
    OrganizationDetailUpdateView,
    OrganizationGigsAPIView,
    OrganizationListCreateView,
    OrganizationSoftDeleteView,
    UserGigHistoryView,
    UserOrganizationGigListView,
    UserOrganizationListCreateView,
    VerifyGigView,
    WorkerSearchAPIView,
)
from .certificate import CertificateJSONView, CertificateLinkView, certificate_page  # noqa: F401
from .ratings import CompletedGigsView, DisputeListCreateView, RateGigView, ResolveDisputeView  # noqa: F401
from .ussd import ussd_callback  # noqa: F401
from .gigs import GigsAvailableDeleteView  # noqa: F401
from .hiring import (ApplyView, CheckInView, DecideApplicationView, MyApplicationsView,  # noqa: F401
                     MyCheckInsTodayView, OnSiteTodayView, PostApplicationsView)
from .workforce import (ActivityView, AttendanceView, AvailableWorkersView, BudgetsView, BulkVerifyView,  # noqa: F401
                        CrewDeleteView, CrewListView, DeleteAccountView, ExportMyDataView, FundiCompletedView,
                        FundiStatementView, IncidentListCreateView, InviteWorkerView, JobAlertDeleteView,
                        JobAlertListCreateView, NotificationListView, NotificationReadView, PayrollView, RateSiteView,
                        RejectGigView, ResolveIncidentView, RespondInvitationView, SavedPostsView, SavePostView,
                        SiteRatingsView, ToggleJobPostView, WithdrawApplicationView, WorkProfileView)
