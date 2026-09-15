"""Manual outreach text assistance; never sends or records contact."""
from .builder import TemplateOutreachGenerator, context_from_lead
from .models import OutreachContext, OutreachGenerator, OutreachRequest, OutreachResult

__all__ = ["OutreachContext", "OutreachRequest", "OutreachResult", "OutreachGenerator", "TemplateOutreachGenerator", "context_from_lead"]
