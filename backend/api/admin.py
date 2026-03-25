from django.contrib import admin

from .models import (
    Assignment,
    AuditEvent,
    Case,
    Claim,
    ClaimRelationship,
    ClaimScore,
    Investigator,
    Outcome,
    ScoringRule,
)


admin.site.register(Claim)
admin.site.register(ScoringRule)
admin.site.register(ClaimScore)
admin.site.register(Investigator)
admin.site.register(Case)
admin.site.register(Assignment)
admin.site.register(ClaimRelationship)
admin.site.register(Outcome)
admin.site.register(AuditEvent)
