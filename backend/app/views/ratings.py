"""Contractor ratings of completed gigs, and gig disputes."""
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from ..models import Gig, GigDispute, GigHistory, GigRating
from ..permissions import owns_organization


class GigRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = GigRating
        fields = ["id", "history", "stars", "comment", "rated_by", "created_at"]
        read_only_fields = ["history", "rated_by", "created_at"]


class GigDisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GigDispute
        fields = ["id", "gig", "history", "reason", "status", "resolution", "raised_by", "resolved_by",
                  "created_at", "resolved_at"]
        read_only_fields = ["status", "resolution", "raised_by", "resolved_by", "created_at", "resolved_at"]


class RateGigView(APIView):
    """POST {"stars": 1-5, "comment": ""}: the site's contractor rates a completed gig (once; updates allowed)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, history_id):
        try:
            history = GigHistory.objects.select_related("organization").get(pk=history_id)
        except GigHistory.DoesNotExist:
            return Response({"detail": "Completed gig not found."}, status=status.HTTP_404_NOT_FOUND)
        if not owns_organization(request.user, history.organization) or request.user.id == history.worker_id:
            return Response({"detail": "Only the contractor who ran this site can rate the work."},
                            status=status.HTTP_403_FORBIDDEN)
        existing = GigRating.objects.filter(history=history).first()
        s = GigRatingSerializer(existing, data=request.data, partial=bool(existing))
        s.is_valid(raise_exception=True)
        s.save(history=history, rated_by=request.user)
        return Response(s.data, status=status.HTTP_200_OK if existing else status.HTTP_201_CREATED)


class DisputeListCreateView(APIView):
    """GET: your disputes (staff: all). POST {"gig"|"history": id, "reason": ...}."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = GigDispute.objects.all()
        if not request.user.is_staff:
            qs = qs.filter(Q(raised_by=request.user) | Q(gig__organization__owner=request.user)
                           | Q(history__organization__owner=request.user) | Q(gig__worker=request.user)
                           | Q(history__worker=request.user))
        return Response(GigDisputeSerializer(qs.distinct(), many=True).data)

    def post(self, request):
        s = GigDisputeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        target = s.validated_data.get("gig") or s.validated_data.get("history")
        if not target or (s.validated_data.get("gig") and s.validated_data.get("history")):
            return Response({"detail": "Give exactly one of gig or history."}, status=status.HTTP_400_BAD_REQUEST)
        if not (request.user.id == target.worker_id or owns_organization(request.user, target.organization)):
            return Response({"detail": "You can only dispute your own gigs or gigs at your sites."},
                            status=status.HTTP_403_FORBIDDEN)
        s.save(raised_by=request.user)
        return Response(s.data, status=status.HTTP_201_CREATED)


class ResolveDisputeView(APIView):
    """Staff: POST {"status": "resolved"|"rejected", "resolution": "..."}."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            d = GigDispute.objects.get(pk=pk)
        except GigDispute.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        new_status = request.data.get("status")
        if new_status not in ("resolved", "rejected"):
            return Response({"detail": "status must be resolved or rejected"}, status=status.HTTP_400_BAD_REQUEST)
        d.status, d.resolution = new_status, request.data.get("resolution", "")
        d.resolved_by, d.resolved_at = request.user, timezone.now()
        d.save()
        return Response(GigDisputeSerializer(d).data)
