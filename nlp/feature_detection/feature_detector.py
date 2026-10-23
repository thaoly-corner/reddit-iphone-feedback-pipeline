"""
iPhone Feature Category Detection based on Domain Taxonomy.
"""
from config.pipeline_config import DomainTaxonomyConfig


def detect_feature_category(
    text: str,
    taxonomy_cfg: DomainTaxonomyConfig = DomainTaxonomyConfig()
) -> str:
    """Detect primary iPhone feature category from post text."""
    lower_txt = (text or "").lower()
    for feature_cat, issues_dict in taxonomy_cfg.issue_taxonomy.items():
        for _, keywords in issues_dict.items():
            if any(kw in lower_txt for kw in keywords):
                return feature_cat
    return "General Discussion"
