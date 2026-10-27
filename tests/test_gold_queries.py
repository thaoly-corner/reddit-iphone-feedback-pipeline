"""Check the new aggregation SQL with SQLite in memory, without starting Spark."""

import sqlite3

import pytest

from config.gold_marts import GOLD_MART_NAMES, LEGACY_GOLD_MART_NAMES
from processing.batch.silver_to_gold.gold_queries import RECURRING_ISSUES_SQL, SUPPORT_DEMAND_SQL


@pytest.fixture
def connection():
    with sqlite3.connect(":memory:") as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("""CREATE TABLE _voc_recurring_input (
            post_id TEXT, issue_category TEXT, feedback_year INT, feedback_month INT
        )""")
        conn.execute("""CREATE TABLE _voc_support_input (
            post_id TEXT, is_question BOOLEAN, support_category TEXT,
            feedback_year INT, feedback_month INT, iphone_model TEXT, ios_version TEXT,
            sentiment_score REAL, reddit_score INT, num_comments INT, engagement_score INT
        )""")
        yield conn


def test_recurring_means_distinct_months_including_different_years(connection) -> None:
    connection.executemany("INSERT INTO _voc_recurring_input VALUES (?, ?, ?, ?)", [
        ("a", "Battery Drain", 2026, 1), ("b", "Battery Drain", 2026, 1),
        ("c", "Battery Drain", 2027, 1),
        ("d", "Green Line", 2026, 1), ("e", "Green Line", 2026, 1),
        ("f", "Non-Defect / General Inquiry", 2026, 1),
        ("g", "Battery Drain", 2026, None),
    ])
    rows = [dict(row) for row in connection.execute(RECURRING_ISSUES_SQL)]
    assert len(rows) == 3
    battery = sorted((row for row in rows if row["issue_category"] == "Battery Drain"), key=lambda row: row["feedback_year"])
    assert [row["issue_count"] for row in battery] == [2, 1]
    assert all(row["active_period_count"] == 2 and row["recurrence_count"] == 1 and row["is_recurring"] for row in battery)
    single = next(row for row in rows if row["issue_category"] == "Green Line")
    assert single["issue_count"] == 2
    assert single["active_period_count"] == 1
    assert single["recurrence_count"] == 0
    assert not single["is_recurring"]


def test_support_counts_only_questions_with_model_and_os_dimensions(connection) -> None:
    connection.executemany("INSERT INTO _voc_support_input VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
        ("a", True, "Battery Support", 2026, 1, "iPhone 16", "iOS 18", -0.8, 10, 2, 14),
        ("b", True, "Battery Support", 2026, 1, "iPhone 16", "iOS 18", -0.2, 20, 4, 28),
        ("c", False, "Battery Support", 2026, 1, "iPhone 16", "iOS 18", 1.0, 500, 0, 500),
        ("d", True, "Battery Support", 2026, 1, "iPhone 17", "iOS 26", 0.0, 5, 1, 7),
        ("e", True, "Other Support", 2026, 2, "Other", "Unspecified", 0.0, 1, 0, 1),
    ])
    rows = [dict(row) for row in connection.execute(SUPPORT_DEMAND_SQL)]
    assert len(rows) == 3
    assert sum(row["question_count"] for row in rows) == 4
    model16 = next(row for row in rows if row["iphone_model"] == "iPhone 16")
    assert model16 == {
        "support_category": "Battery Support", "feedback_year": 2026, "feedback_month": 1,
        "iphone_model": "iPhone 16", "ios_version": "iOS 18", "question_count": 2,
        "avg_sentiment_score": -0.5, "avg_reddit_score": 15.0,
        "avg_num_comments": 3.0, "avg_engagement_score": 21.0,
    }


def test_empty_inputs_produce_empty_marts(connection) -> None:
    assert list(connection.execute(RECURRING_ISSUES_SQL)) == []
    assert list(connection.execute(SUPPORT_DEMAND_SQL)) == []


def test_all_legacy_mart_names_preserved() -> None:
    assert len(LEGACY_GOLD_MART_NAMES) == 8
    assert len(GOLD_MART_NAMES) == len(set(GOLD_MART_NAMES)) == 10
    assert GOLD_MART_NAMES[:8] == LEGACY_GOLD_MART_NAMES
    assert GOLD_MART_NAMES[-2:] == ("recurring_issues", "support_demand")
