"""Stable Gold output names shared by processing and serving adapters."""

LEGACY_GOLD_MART_NAMES = (
    "feedback_volume",
    "issue_summary",
    "emerging_issues",
    "sentiment_summary",
    "feature_feedback",
    "high_impact_complaints",
    "issue_trends",
    "model_comparison",
)

GOLD_MART_NAMES = LEGACY_GOLD_MART_NAMES + ("recurring_issues", "support_demand")
