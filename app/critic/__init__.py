"""Investigation critic (quality control)."""

from app.critic.engine import critique_investigation
from app.models.critic import CriticIssue, CriticVerdict

__all__ = ["CriticIssue", "CriticVerdict", "critique_investigation"]
