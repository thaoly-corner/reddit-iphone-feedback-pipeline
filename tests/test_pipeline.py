"""
Unit Tests for Configuration, Entity Extraction, Issue Taxonomy, and Sentiment Scoring.
"""
from config.pipeline_config import DomainTaxonomyConfig, PipelineExecutionConfig
from nlp.issue_classification.issue_classifier import classify_feature_and_issue
from nlp.sentiment.alternatives.lexicon_sentiment import score_lexicon_sentiment


def test_default_pipeline_config():
    cfg = PipelineExecutionConfig()
    assert cfg.silver_engine == "pyspark_roberta"
    assert cfg.batch_gold_engine == "spark_sql"
    assert cfg.stream_engine == "apache_flink"
    assert cfg.serving_backend == "postgres"
    assert cfg.schema_paradigm == "galaxy"


def test_issue_classification():
    tax = DomainTaxonomyConfig()
    feat, issue = classify_feature_and_issue(
        "My phone gets hot and battery drain is terrible after iOS 18.2.",
        taxonomy_cfg=tax
    )
    assert feat == "Battery & Thermal"
    assert issue == "Rapid Battery Drain"


def test_lexicon_sentiment():
    lbl_neg, sc_neg = score_lexicon_sentiment("Battery drain is horrible and phone is overheating")
    assert lbl_neg == "NEGATIVE"
    assert sc_neg < 0

    lbl_pos, sc_pos = score_lexicon_sentiment("Camera is amazing and performance is super smooth")
    assert lbl_pos == "POSITIVE"
    assert sc_pos > 0
