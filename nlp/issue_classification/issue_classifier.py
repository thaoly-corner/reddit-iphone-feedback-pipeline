"""
Product Issue Classification based on Domain Taxonomy (Battery, Thermal, Display, Camera, etc.).
"""
from typing import Tuple
from config.pipeline_config import DomainTaxonomyConfig


def classify_feature_and_issue(
    text: str,
    taxonomy_cfg: DomainTaxonomyConfig = DomainTaxonomyConfig()
) -> Tuple[str, str]:
    """Return (feature_category, issue_category) matched from DomainTaxonomyConfig."""
    lower_txt = (text or "").lower()
    for feature_cat, issues_dict in taxonomy_cfg.issue_taxonomy.items():
        for issue_name, keywords in issues_dict.items():
            if any(kw in lower_txt for kw in keywords):
                return feature_cat, issue_name
    return "General Discussion", "Non-Defect / General Inquiry"
