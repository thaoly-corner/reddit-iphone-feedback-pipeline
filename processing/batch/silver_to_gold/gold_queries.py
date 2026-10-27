"""SQL for the additive Gold marts, also testable with an in-memory SQL engine."""

RECURRING_ISSUES_SQL = """
WITH monthly AS (
    SELECT issue_category, feedback_year, feedback_month, COUNT(post_id) AS issue_count
    FROM _voc_recurring_input
    WHERE issue_category IS NOT NULL
      AND issue_category <> 'Non-Defect / General Inquiry'
      AND feedback_year IS NOT NULL
      AND feedback_month BETWEEN 1 AND 12
    GROUP BY issue_category, feedback_year, feedback_month
), periods AS (
    SELECT *, COUNT(*) OVER (PARTITION BY issue_category) AS active_period_count
    FROM monthly
)
SELECT issue_category, feedback_year, feedback_month, issue_count,
       active_period_count, active_period_count - 1 AS recurrence_count,
       active_period_count >= 2 AS is_recurring
FROM periods
"""

SUPPORT_DEMAND_SQL = """
SELECT support_category, feedback_year, feedback_month, iphone_model, ios_version,
       COUNT(post_id) AS question_count,
       ROUND(AVG(sentiment_score), 4) AS avg_sentiment_score,
       ROUND(AVG(reddit_score), 2) AS avg_reddit_score,
       ROUND(AVG(num_comments), 2) AS avg_num_comments,
       ROUND(AVG(engagement_score), 2) AS avg_engagement_score
FROM _voc_support_input
WHERE is_question = TRUE
GROUP BY support_category, feedback_year, feedback_month, iphone_model, ios_version
"""
