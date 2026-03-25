from rest_framework import serializers

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


class ClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'status']


class ClaimIngestSerializer(serializers.Serializer):
    """
    Payload used to ingest a claim into the system.
    """

    external_id = serializers.CharField(max_length=128)
    claimant_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    claimant_email = serializers.EmailField(required=False, allow_blank=True)
    claimant_phone = serializers.CharField(max_length=64, required=False, allow_blank=True)
    policy_number = serializers.CharField(max_length=128, required=False, allow_blank=True)
    loss_date = serializers.DateField(required=False, allow_null=True)
    loss_type = serializers.CharField(max_length=128, required=False, allow_blank=True)
    loss_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    raw_payload = serializers.JSONField(required=False, allow_null=True)


class ScoringRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScoringRule
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class ClaimScoreSerializer(serializers.ModelSerializer):
    claim_external_id = serializers.CharField(source='claim.external_id', read_only=True)

    class Meta:
        model = ClaimScore
        fields = '__all__'
        read_only_fields = ['id', 'computed_at']


class InvestigatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Investigator
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class CaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class AssignmentSerializer(serializers.ModelSerializer):
    claim_external_id = serializers.CharField(source='claim.external_id', read_only=True)
    investigator_username = serializers.CharField(source='investigator.username', read_only=True)

    class Meta:
        model = Assignment
        fields = '__all__'
        read_only_fields = ['id', 'assigned_at', 'updated_at']


class ClaimRelationshipSerializer(serializers.ModelSerializer):
    source_external_id = serializers.CharField(source='source_claim.external_id', read_only=True)
    target_external_id = serializers.CharField(source='target_claim.external_id', read_only=True)

    class Meta:
        model = ClaimRelationship
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class OutcomeSerializer(serializers.ModelSerializer):
    claim_external_id = serializers.CharField(source='claim.external_id', read_only=True)
    investigator_username = serializers.CharField(source='investigator.username', read_only=True)

    class Meta:
        model = Outcome
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class ScoreRunRequestSerializer(serializers.Serializer):
    """
    Trigger a scoring run over a specific claim.
    """

    claim_external_id = serializers.CharField(max_length=128)


class ScoreRunResponseSerializer(serializers.Serializer):
    claim_external_id = serializers.CharField(max_length=128)
    total_score = serializers.IntegerField()
    matched_rules = serializers.JSONField()
    computed_at = serializers.DateTimeField()

