"""
Alternative Sentiment Analysis Engine ('pyspark_lexicon'):
Negation-Aware Rule/VADER-style Polarity Lexicon and Distributed PySpark Arrow Pandas UDF.
"""
import re
from typing import Iterator, Tuple
import pandas as pd
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, FloatType


NEG_LEXICON = {
    "broke", "broken", "issue", "issues", "problem", "problems", "bug", "bugs", "worst",
    "bad", "lag", "lagging", "drain", "draining", "bend", "bending", "bent", "horrible",
    "useless", "denies", "sad", "mistake", "mistakes", "typos", "typo", "slip", "slipped",
    "dumb", "overheat", "overheating", "hot", "freeze", "freezing", "crash", "crashing",
    "flicker", "blur", "blurry", "slow", "annoying", "disappointed", "defect", "fail"
}
POS_LEXICON = {
    "glad", "great", "love", "smooth", "amazing", "best", "improved", "perfect",
    "good", "fast", "awesome", "helpful", "appreciated", "happy", "excellent", "solid"
}
NEGATION_WORDS = {"not", "no", "never", "neither", "barely", "hardly", "doesn't", "don't", "isn't", "wasn't"}

sentiment_output_schema = StructType([
    StructField("sentiment", StringType(), True),
    StructField("sentiment_score", FloatType(), True)
])


def score_lexicon_sentiment(text: str) -> Tuple[str, float]:
    """
    Bo cham diem cam xuc dua tren tu dien phan cuc co xu ly phu dinh (VADER/Lexicon-style),
    toc do cuc nhanh (O(L)) va khong phu thuoc GPU.
    """
    tokens = re.findall(r"\w+|n't", (text or "").lower())
    pos_score = 0.0
    neg_score = 0.0
    for idx, tok in enumerate(tokens):
        prev_negated = any(tokens[max(0, idx - 3):idx][j] in NEGATION_WORDS for j in range(len(tokens[max(0, idx - 3):idx])))
        if tok in POS_LEXICON:
            if prev_negated:
                neg_score += 0.35
            else:
                pos_score += 0.38
        elif tok in NEG_LEXICON:
            if prev_negated:
                pos_score += 0.25
            else:
                neg_score += 0.42

    net = pos_score - neg_score
    if net <= -0.15:
        return ("NEGATIVE", round(max(-1.0, net), 4))
    elif net >= 0.15:
        return ("POSITIVE", round(min(1.0, net), 4))
    return ("NEUTRAL", 0.0)


@F.pandas_udf(sentiment_output_schema)
def lexicon_sentiment_pandas_udf(text_series_iter: Iterator[pd.Series]) -> Iterator[pd.DataFrame]:
    """
    Engine 2 (Thay the 1): Vectorized Pandas UDF su dung Lexicon-based Sentiment (VADER-style)
    giup tang toc do xu ly tren CPU ma khong can tai trong so mo hinh Deep Learning.
    """
    for series in text_series_iter:
        texts = series.fillna("").astype(str).tolist()
        labels, scores = [], []
        for t in texts:
            lbl, sc = score_lexicon_sentiment(t)
            labels.append(lbl)
            scores.append(sc)
        yield pd.DataFrame({"sentiment": labels, "sentiment_score": scores})
