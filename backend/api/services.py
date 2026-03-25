import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.db.models import Q

from .models import Claim, ClaimRelationship, ClaimScore, ScoringRule


def _get_field_value(claim: Claim, field: str) -> Any:
    """
    Return value from a claim for a given field. Supports:
      - direct model fields (e.g., "loss_amount")
      - payload lookup via "payload.<key>" (e.g., "payload.vehicle.vin")
    """
    if field.startswith('payload.'):
        path = field.split('.')[1:]
        cur = claim.raw_payload or {}
        for p in path:
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
        return cur
    return getattr(claim, field, None)


def _coerce_number(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def _evaluate_condition(claim: Claim, condition: Dict[str, Any]) -> bool:
    """
    Evaluate a rule condition against a claim.

    Supported schema:
      { "field": "...", "operator": "...", "value": ... }
    """
    field = condition.get('field')
    operator = condition.get('operator')
    value = condition.get('value')

    if not field or not operator:
        return False

    actual = _get_field_value(claim, field)

    if operator == 'exists':
        return actual is not None and actual != ''

    if operator in {'gt', 'gte', 'lt', 'lte'}:
        actual_n = _coerce_number(actual)
        value_n = _coerce_number(value)
        if actual_n is None or value_n is None:
            return False
        if operator == 'gt':
            return actual_n > value_n
        if operator == 'gte':
            return actual_n >= value_n
        if operator == 'lt':
            return actual_n < value_n
        if operator == 'lte':
            return actual_n <= value_n

    if operator == 'eq':
        return actual == value
    if operator == 'neq':
        return actual != value
    if operator == 'contains':
        if actual is None:
            return False
        return str(value).lower() in str(actual).lower()
    if operator == 'in':
        if not isinstance(value, list):
            return False
        return actual in value
    if operator == 'regex':
        if actual is None:
            return False
        try:
            return re.search(str(value), str(actual)) is not None
        except re.error:
            return False

    return False


# PUBLIC_INTERFACE
@transaction.atomic
def score_claim(claim: Claim) -> ClaimScore:
    """
    Score a claim using enabled ScoringRules.

    Returns the persisted ClaimScore record.
    """
    rules = ScoringRule.objects.filter(enabled=True).order_by('priority', 'id')
    total = 0
    matched: List[Dict[str, Any]] = []

    for rule in rules:
        try:
            if _evaluate_condition(claim, rule.condition):
                total += int(rule.score_delta)
                matched.append(
                    {
                        'rule_id': rule.id,
                        'rule_name': rule.name,
                        'score_delta': rule.score_delta,
                    }
                )
        except Exception:
            # Rule condition errors should not crash the scoring run;
            # treat as non-match.
            continue

    score = ClaimScore.objects.create(claim=claim, total_score=total, matched_rules=matched)

    # Update claim status for queueing purposes.
    claim.status = 'scored'
    claim.save(update_fields=['status', 'updated_at'])

    return score


# PUBLIC_INTERFACE
@transaction.atomic
def generate_relationships_for_claim(claim: Claim) -> int:
    """
    Generate simple relationships between this claim and other claims.

    Links by: claimant_email, claimant_phone, policy_number.
    Returns number of relationships created.
    """
    created = 0

    def _link(other_qs, rel_type: str, key: str) -> None:
        nonlocal created
        for other in other_qs:
            if other.id == claim.id:
                continue
            obj, was_created = ClaimRelationship.objects.get_or_create(
                source_claim=claim,
                target_claim=other,
                relationship_type=rel_type,
                key=key,
                defaults={'weight': 1},
            )
            if was_created:
                created += 1

    if claim.claimant_email:
        matches = Claim.objects.filter(~Q(id=claim.id), claimant_email=claim.claimant_email)
        _link(matches, 'same_email', claim.claimant_email)

    if claim.claimant_phone:
        matches = Claim.objects.filter(~Q(id=claim.id), claimant_phone=claim.claimant_phone)
        _link(matches, 'same_phone', claim.claimant_phone)

    if claim.policy_number:
        matches = Claim.objects.filter(~Q(id=claim.id), policy_number=claim.policy_number)
        _link(matches, 'same_policy', claim.policy_number)

    return created


# PUBLIC_INTERFACE
def get_queue_queryset(min_score: Optional[int] = None):
    """
    Return a queryset of claims for the investigation queue.

    Queue logic: show latest score for each claim; allow optional min_score filtering.
    """
    qs = Claim.objects.all().order_by('-updated_at')
    if min_score is None:
        return qs
    # Filter claims that have *any* score run meeting threshold (simple approach).
    return qs.filter(score_runs__total_score__gte=min_score).distinct()

