from django.urls import path

from .views import (
    AnalyticsSummaryView,
    AssignmentListCreateView,
    CaseListCreateView,
    ClaimDetailView,
    ClaimIngestView,
    ClaimListView,
    ClaimRelationshipsView,
    ClaimScoreHistoryView,
    InvestigatorListCreateView,
    OutcomeCreateUpdateView,
    QueueView,
    ScoreClaimView,
    ScoringRuleDetailView,
    ScoringRuleListCreateView,
    health,
)

urlpatterns = [
    # Health
    path('health/', health, name='Health'),
    # Ingestion / Claims
    path('claims/ingest/', ClaimIngestView.as_view(), name='ClaimIngest'),
    path('claims/', ClaimListView.as_view(), name='ClaimList'),
    path('claims/<str:external_id>/', ClaimDetailView.as_view(), name='ClaimDetail'),
    # Rules & Scoring
    path('rules/', ScoringRuleListCreateView.as_view(), name='RuleListCreate'),
    path('rules/<int:pk>/', ScoringRuleDetailView.as_view(), name='RuleDetail'),
    path('scoring/run/', ScoreClaimView.as_view(), name='ScoreRun'),
    path('scoring/history/<str:external_id>/', ClaimScoreHistoryView.as_view(), name='ScoreHistory'),
    # Queue
    path('queue/', QueueView.as_view(), name='Queue'),
    # Assignments / Cases / Investigators
    path('investigators/', InvestigatorListCreateView.as_view(), name='InvestigatorListCreate'),
    path('cases/', CaseListCreateView.as_view(), name='CaseListCreate'),
    path('assignments/', AssignmentListCreateView.as_view(), name='AssignmentListCreate'),
    # Network relationships
    path('relationships/<str:external_id>/', ClaimRelationshipsView.as_view(), name='ClaimRelationships'),
    # Outcomes
    path('outcomes/<str:external_id>/', OutcomeCreateUpdateView.as_view(), name='OutcomeUpsert'),
    # Analytics
    path('analytics/summary/', AnalyticsSummaryView.as_view(), name='AnalyticsSummary'),
]
