"""Staff back office: identity review, disputes, and read-only financial/score records."""
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from django.utils.html import format_html

from . import identity
from .models import (CreditScoreHistory, Gig, GigDispute, GigHistory, GigRating, JobType, MpesaNewTransaction,
                     Organization, Payment, User, VerificationRequest)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "full_name", "account_type", "credit_score", "is_verified", "id_status", "is_staff")
    list_filter = ("account_type", "is_verified", "is_staff", "is_active")
    search_fields = ("username", "email", "full_name", "phone", "national_id")
    readonly_fields = ("credit_score", "current_verification")  # changed only via scoring / ID review
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Fundi / Jenga", {"fields": ("account_type", "full_name", "phone", "national_id", "county",
                                      "constituency", "ward", "profile_pic", "is_verified", "credit_score",
                                      "current_verification")}),
    )

    @admin.display(description="ID")
    def id_status(self, obj):
        v = obj.current_verification
        return v.status if v else "-"


def _preview(field_file):
    if not field_file:
        return "-"
    # Staff are signed in to the admin, so the private-media view serves them the file.
    return format_html('<a href="{0}" target="_blank"><img src="{0}" style="max-height:220px;border-radius:6px"></a>',
                       field_file.url)


@admin.register(VerificationRequest)
class VerificationRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username", "user__full_name", "user__national_id")
    readonly_fields = ("user", "status", "front_preview", "back_preview", "selfie_preview", "created_at", "updated_at")
    fields = ("user", "status", "rejection_reason", "front_preview", "back_preview", "selfie_preview",
              "created_at", "updated_at")
    actions = ("approve_selected", "reject_selected")

    def has_add_permission(self, request):
        return False

    @admin.display(description="ID front")
    def front_preview(self, obj):
        return _preview(obj.id_front)

    @admin.display(description="ID back")
    def back_preview(self, obj):
        return _preview(obj.id_back)

    @admin.display(description="Selfie")
    def selfie_preview(self, obj):
        return _preview(obj.selfie)

    @admin.action(description="Approve selected (awards +20 once)")
    def approve_selected(self, request, queryset):
        n = sum(identity.approve(v) for v in queryset.select_related("user"))
        self.message_user(request, f"{n} newly approved.", messages.SUCCESS)

    @admin.action(description="Reject selected (uses each request's rejection reason)")
    def reject_selected(self, request, queryset):
        for v in queryset.select_related("user"):
            identity.reject(v, v.rejection_reason or "Rejected by staff")
        self.message_user(request, f"{queryset.count()} rejected.", messages.WARNING)


@admin.register(GigDispute)
class GigDisputeAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "raised_by", "gig", "history", "created_at", "resolved_by")
    list_filter = ("status",)
    readonly_fields = ("gig", "history", "raised_by", "reason", "created_at", "resolved_by", "resolved_at")
    fields = ("status", "raised_by", "gig", "history", "reason", "resolution", "created_at", "resolved_by",
              "resolved_at")

    def save_model(self, request, obj, form, change):
        if "status" in form.changed_data and obj.status != "open":
            obj.resolved_by, obj.resolved_at = request.user, timezone.now()
        super().save_model(request, obj, form, change)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CreditScoreHistory)
class CreditScoreHistoryAdmin(ReadOnlyAdmin):
    list_display = ("timestamp", "user", "action", "change", "new_score")
    list_filter = ("action",)
    search_fields = ("user__username",)


@admin.register(MpesaNewTransaction)
class MpesaNewTransactionAdmin(ReadOnlyAdmin):
    list_display = ("transaction_date", "user", "amount", "mpesa_receipt_number", "result_code", "phone_number")
    search_fields = ("mpesa_receipt_number", "phone_number", "user__username")


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "county", "is_active", "created_at")
    list_filter = ("is_active", "county")
    search_fields = ("name", "owner__username")


@admin.register(Gig)
class GigAdmin(admin.ModelAdmin):
    list_display = ("id", "worker", "organization", "job_type", "start_date", "is_verified", "verified_by")
    list_filter = ("is_verified",)
    search_fields = ("worker__username", "organization__name")
    readonly_fields = ("is_verified", "verified_by")  # verification only through the contractor flow


@admin.register(GigHistory)
class GigHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "worker", "organization", "job_type", "start_date", "is_verified")
    search_fields = ("worker__username", "organization__name")


admin.site.register(JobType)
admin.site.register(Payment)
admin.site.register(GigRating)
admin.site.site_header = "Fundi / Jenga Pro administration"
