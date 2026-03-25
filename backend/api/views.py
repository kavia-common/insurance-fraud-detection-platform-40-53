from django.db.models import Count, Sum
from django.utils import timezone
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Assignment,
    Case,
    Claim,
    ClaimRelationship,
    ClaimScore,
    Investigator,
    Outcome,
    ScoringRule,
)
from .serializers import (
    AssignmentSerializer,
    CaseSerializer,
    ClaimIngestSerializer,
    ClaimRelationshipSerializer,
    ClaimScoreSerializer,
    ClaimSerializer,
    InvestigatorSerializer,
    OutcomeSerializer,
    ScoreRunRequestSerializer,
    ScoreRunResponseSerializer,
    ScoringRuleSerializer,
)
from .services import generate_relationships_for_claim, get_queue_queryset, score_claim


@api_view(['GET'])
def health(request):
    return Response({"message": "Server is up!"})


class ClaimIngestView(APIView):
    """
    Ingest or update a claim.

    If a claim with external_id already exists, it is updated with provided fields.
    """

    @swagger_auto_schema(
        operation_id='claim_ingest',
        operation_summary='Ingest claim',
        operation_description='Create or update a claim by external_id; stores raw payload.',
        tags=['ingestion'],
        request_body=ClaimIngestSerializer,
        responses={201: ClaimSerializer, 200: ClaimSerializer},
    )
    def post(self, request):
        serializer = ClaimIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        claim, created = Claim.objects.get_or_create(external_id=data['external_id'])
        # Update mutable fields
        for f in [
            'claimant_name',
            'claimant_email',
            'claimant_phone',
            'policy_number',
            'loss_date',
            'loss_type',
            'loss_amount',
            'raw_payload',
        ]:
            if f in data:
                setattr(claim, f, data.get(f))
        claim.status = 'new'
        claim.save()

        out = ClaimSerializer(claim).data
        return Response(out, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class ClaimListView(generics.ListAPIView):
    queryset = Claim.objects.all().order_by('-created_at')
    serializer_class = ClaimSerializer

    @swagger_auto_schema(
        operation_id='claim_list',
        operation_summary='List claims',
        tags=['claims'],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ClaimDetailView(generics.RetrieveAPIView):
    queryset = Claim.objects.all()
    serializer_class = ClaimSerializer
    lookup_field = 'external_id'

    @swagger_auto_schema(
        operation_id='claim_get',
        operation_summary='Get claim',
        tags=['claims'],
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ScoringRuleListCreateView(generics.ListCreateAPIView):
    queryset = ScoringRule.objects.all()
    serializer_class = ScoringRuleSerializer

    @swagger_auto_schema(operation_summary='List scoring rules', tags=['rules'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary='Create scoring rule', tags=['rules'])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class ScoringRuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ScoringRule.objects.all()
    serializer_class = ScoringRuleSerializer

    @swagger_auto_schema(operation_summary='Get scoring rule', tags=['rules'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary='Update scoring rule', tags=['rules'])
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary='Partial update scoring rule', tags=['rules'])
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary='Delete scoring rule', tags=['rules'])
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class ScoreClaimView(APIView):
    @swagger_auto_schema(
        operation_id='score_run',
        operation_summary='Score a claim',
        operation_description='Runs enabled rules over a claim and persists a ClaimScore snapshot.',
        tags=['scoring'],
        request_body=ScoreRunRequestSerializer,
        responses={200: ScoreRunResponseSerializer},
    )
    def post(self, request):
        serializer = ScoreRunRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        external_id = serializer.validated_data['claim_external_id']

        try:
            claim = Claim.objects.get(external_id=external_id)
        except Claim.DoesNotExist:
            return Response(
                {'detail': 'Claim not found.'}, status=status.HTTP_404_NOT_FOUND
            )

        score_obj = score_claim(claim)
        generate_relationships_for_claim(claim)

        resp = {
            'claim_external_id': claim.external_id,
            'total_score': score_obj.total_score,
            'matched_rules': score_obj.matched_rules,
            'computed_at': score_obj.computed_at,
        }
        return Response(resp, status=status.HTTP_200_OK)


class ClaimScoreHistoryView(generics.ListAPIView):
    serializer_class = ClaimScoreSerializer

    def get_queryset(self):
        external_id = self.kwargs['external_id']
        return ClaimScore.objects.filter(claim__external_id=external_id).order_by('-computed_at')

    @swagger_auto_schema(operation_summary='Get claim score history', tags=['scoring'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class QueueView(generics.ListAPIView):
    serializer_class = ClaimSerializer

    min_score_param = openapi.Parameter(
        'min_score',
        openapi.IN_QUERY,
        description='Optional minimum score threshold for queue filtering',
        type=openapi.TYPE_INTEGER,
        required=False,
    )

    @swagger_auto_schema(operation_summary='Get investigation queue', tags=['queue'], manual_parameters=[min_score_param])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        min_score = self.request.query_params.get('min_score')
        try:
            min_score_int = int(min_score) if min_score is not None else None
        except ValueError:
            min_score_int = None
        return get_queue_queryset(min_score=min_score_int)


class InvestigatorListCreateView(generics.ListCreateAPIView):
    queryset = Investigator.objects.all().order_by('username')
    serializer_class = InvestigatorSerializer

    @swagger_auto_schema(operation_summary='List investigators', tags=['investigators'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary='Create investigator', tags=['investigators'])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class CaseListCreateView(generics.ListCreateAPIView):
    queryset = Case.objects.all().order_by('-created_at')
    serializer_class = CaseSerializer

    @swagger_auto_schema(operation_summary='List cases', tags=['cases'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary='Create case', tags=['cases'])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class AssignmentListCreateView(generics.ListCreateAPIView):
    queryset = Assignment.objects.select_related('claim', 'investigator', 'case').all().order_by('-assigned_at')
    serializer_class = AssignmentSerializer

    @swagger_auto_schema(operation_summary='List assignments', tags=['assignments'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @swagger_auto_schema(operation_summary='Create assignment', tags=['assignments'])
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class ClaimRelationshipsView(generics.ListAPIView):
    serializer_class = ClaimRelationshipSerializer

    def get_queryset(self):
        external_id = self.kwargs['external_id']
        return ClaimRelationship.objects.filter(source_claim__external_id=external_id).order_by('-created_at')

    @swagger_auto_schema(operation_summary='List claim relationships', tags=['relationships'])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class OutcomeCreateUpdateView(APIView):
    @swagger_auto_schema(
        operation_id='outcome_upsert',
        operation_summary='Create/update outcome',
        operation_description='Upserts an outcome for the given claim external_id.',
        tags=['outcomes'],
        request_body=OutcomeSerializer,
        responses={200: OutcomeSerializer, 201: OutcomeSerializer},
    )
    def post(self, request, external_id: str):
        try:
            claim = Claim.objects.get(external_id=external_id)
        except Claim.DoesNotExist:
            return Response({'detail': 'Claim not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = OutcomeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        outcome, created = Outcome.objects.update_or_create(
            claim=claim,
            defaults={
                'investigator': data.get('investigator'),
                'outcome_type': data['outcome_type'],
                'loss_avoided_amount': data.get('loss_avoided_amount'),
                'notes': data.get('notes', ''),
            },
        )

        return Response(
            OutcomeSerializer(outcome).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class AnalyticsSummaryView(APIView):
    @swagger_auto_schema(
        operation_id='analytics_summary',
        operation_summary='Analytics summary',
        operation_description='Returns counts and aggregates for dashboard summary tiles.',
        tags=['analytics'],
        responses={200: openapi.Schema(type=openapi.TYPE_OBJECT)},
    )
    def get(self, request):
        total_claims = Claim.objects.count()
        total_scored = ClaimScore.objects.values('claim_id').distinct().count()
        total_assigned = Assignment.objects.values('claim_id').distinct().count()
        total_outcomes = Outcome.objects.count()

        outcomes_by_type = list(
            Outcome.objects.values('outcome_type').annotate(count=Count('id')).order_by('-count')
        )

        loss_avoided = Outcome.objects.aggregate(total=Sum('loss_avoided_amount'))['total'] or 0

        last_30_days = timezone.now() - timezone.timedelta(days=30)
        ingested_30d = Claim.objects.filter(created_at__gte=last_30_days).count()

        return Response(
            {
                'total_claims': total_claims,
                'total_scored_claims': total_scored,
                'total_assigned_claims': total_assigned,
                'total_outcomes': total_outcomes,
                'outcomes_by_type': outcomes_by_type,
                'loss_avoided_total': str(loss_avoided),
                'claims_ingested_last_30_days': ingested_30d,
            }
        )

