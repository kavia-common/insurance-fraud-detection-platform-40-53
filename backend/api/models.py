from django.db import models


class Claim(models.Model):
    """
    A claim record ingested into the platform.

    This is the core object investigators work from. It stores minimal normalized
    details needed for scoring, queueing, and relationship analysis.
    """

    external_id = models.CharField(max_length=128, unique=True)
    claimant_name = models.CharField(max_length=255, blank=True, default='')
    claimant_email = models.EmailField(blank=True, default='')
    claimant_phone = models.CharField(max_length=64, blank=True, default='')
    policy_number = models.CharField(max_length=128, blank=True, default='')
    loss_date = models.DateField(null=True, blank=True)
    loss_type = models.CharField(max_length=128, blank=True, default='')
    loss_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    raw_payload = models.JSONField(null=True, blank=True)

    status = models.CharField(
        max_length=32,
        default='new',
        help_text="Lifecycle: new, scored, queued, assigned, closed, archived",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['external_id']),
            models.Index(fields=['status', '-updated_at']),
            models.Index(fields=['policy_number']),
        ]

    def __str__(self) -> str:
        return f"Claim({self.external_id})"


class ScoringRule(models.Model):
    """
    A configurable rules-based scoring rule.

    Supports simple operators; the backend applies rules over claim fields and/or payload.
    """

    OPERATORS = [
        ('eq', 'equals'),
        ('neq', 'not_equals'),
        ('contains', 'contains'),
        ('gt', 'greater_than'),
        ('gte', 'greater_or_equal'),
        ('lt', 'less_than'),
        ('lte', 'less_or_equal'),
        ('in', 'in_list'),
        ('regex', 'regex'),
        ('exists', 'exists'),
    ]

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, default='')
    enabled = models.BooleanField(default=True)

    # A simple JSON spec describing how to evaluate this rule.
    # Example:
    # {
    #   "field": "loss_amount",
    #   "operator": "gt",
    #   "value": 10000
    # }
    condition = models.JSONField()

    score_delta = models.IntegerField(help_text="Score added when rule matches (can be negative).")
    priority = models.IntegerField(default=100, help_text="Lower number runs earlier.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', 'id']
        indexes = [models.Index(fields=['enabled', 'priority'])]

    def __str__(self) -> str:
        return f"Rule({self.name})"


class ClaimScore(models.Model):
    """A snapshot of a claim scoring run."""

    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='score_runs')
    total_score = models.IntegerField()
    matched_rules = models.JSONField(default=list, help_text="List of matched rule names/ids and deltas.")
    computed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['claim', '-computed_at']),
            models.Index(fields=['-computed_at']),
        ]

    def __str__(self) -> str:
        return f"ClaimScore({self.claim.external_id}, {self.total_score})"


class Investigator(models.Model):
    """An investigator user/profile used for assignments and workload."""

    username = models.CharField(max_length=150, unique=True)
    display_name = models.CharField(max_length=255, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['active'])]

    def __str__(self) -> str:
        return self.username


class Case(models.Model):
    """An investigation case grouping one or more claims."""

    STATUS_CHOICES = [
        ('open', 'open'),
        ('closed', 'closed'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='open')
    priority = models.IntegerField(default=0)

    created_by = models.ForeignKey(
        Investigator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_cases',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['priority', 'status']),
        ]

    def __str__(self) -> str:
        return f"Case({self.id}, {self.status})"


class Assignment(models.Model):
    """Assignment of a claim to an investigator, optionally within a case."""

    STATUS_CHOICES = [
        ('assigned', 'assigned'),
        ('in_progress', 'in_progress'),
        ('completed', 'completed'),
    ]

    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='assignments')
    investigator = models.ForeignKey(Investigator, on_delete=models.CASCADE, related_name='assignments')
    case = models.ForeignKey(Case, on_delete=models.SET_NULL, null=True, blank=True, related_name='assignments')

    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='assigned')
    note = models.TextField(blank=True, default='')

    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('claim', 'investigator', 'case')]
        indexes = [
            models.Index(fields=['investigator', 'status', '-updated_at']),
            models.Index(fields=['claim', '-assigned_at']),
        ]

    def __str__(self) -> str:
        return f"Assignment({self.claim.external_id} -> {self.investigator.username})"


class ClaimRelationship(models.Model):
    """Links claims together by a relationship type and shared identifier."""

    REL_TYPES = [
        ('same_claimant', 'same_claimant'),
        ('same_policy', 'same_policy'),
        ('same_phone', 'same_phone'),
        ('same_email', 'same_email'),
        ('same_address', 'same_address'),
        ('custom', 'custom'),
    ]

    source_claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='relationships_out')
    target_claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name='relationships_in')

    relationship_type = models.CharField(max_length=64, choices=REL_TYPES)
    key = models.CharField(max_length=255, help_text="Shared identifier that caused the link (e.g., phone/email).")
    weight = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('source_claim', 'target_claim', 'relationship_type', 'key')]
        indexes = [
            models.Index(fields=['relationship_type', 'key']),
            models.Index(fields=['source_claim']),
            models.Index(fields=['target_claim']),
        ]

    def __str__(self) -> str:
        return f"Rel({self.source_claim.external_id}->{self.target_claim.external_id},{self.relationship_type})"


class Outcome(models.Model):
    """The resolution/outcome of an investigation for a claim."""

    OUTCOME_TYPES = [
        ('fraud_confirmed', 'fraud_confirmed'),
        ('fraud_suspected', 'fraud_suspected'),
        ('legit', 'legit'),
        ('inconclusive', 'inconclusive'),
        ('withdrawn', 'withdrawn'),
    ]

    claim = models.OneToOneField(Claim, on_delete=models.CASCADE, related_name='outcome')
    investigator = models.ForeignKey(Investigator, on_delete=models.SET_NULL, null=True, blank=True)
    outcome_type = models.CharField(max_length=64, choices=OUTCOME_TYPES)
    loss_avoided_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['outcome_type', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"Outcome({self.claim.external_id},{self.outcome_type})"


class AuditEvent(models.Model):
    """Simple audit/event stream for traceability across ingestion/scoring/assignment/outcomes."""

    EVENT_TYPES = [
        ('ingested', 'ingested'),
        ('scored', 'scored'),
        ('queued', 'queued'),
        ('assigned', 'assigned'),
        ('outcome_recorded', 'outcome_recorded'),
        ('updated', 'updated'),
    ]

    event_type = models.CharField(max_length=64, choices=EVENT_TYPES)
    actor = models.CharField(max_length=255, blank=True, default='')
    claim = models.ForeignKey(Claim, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    case = models.ForeignKey(Case, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')

    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['event_type', '-created_at']),
            models.Index(fields=['claim', '-created_at']),
        ]

    def __str__(self) -> str:
        return f"AuditEvent({self.event_type},{self.created_at})"
