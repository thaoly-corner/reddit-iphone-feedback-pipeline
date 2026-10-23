"""
Main Sentiment Analysis Engine ('pyspark_roberta'):
Vectorized Arrow Pandas UDF running Hugging Face Transformer (cardiffnlp/twitter-roberta-base-sentiment-latest)
with automatic CPU lexicon fallback.
"""
from typing import Iterator
import pandas as pd
from pyspark.sql import functions as F

from nlp.sentiment.alternatives.lexicon_sentiment import (
    sentiment_output_schema,
    score_lexicon_sentiment
)


@F.pandas_udf(sentiment_output_schema)
def transformer_sentiment_udf(text_series_iter: Iterator[pd.Series]) -> Iterator[pd.DataFrame]:
    """
    Engine 1 (Chinh): Vectorized Pandas UDF khoi tao Transformer (cardiffnlp/twitter-roberta-base-sentiment-latest)
    mot lan duy nhat tren moi Spark Worker Partition, kem co che fallback Lexicon an toan.
    """
    use_transformer = False
    nlp_pipe = None
    try:
        import torch
        from transformers import pipeline
        device = 0 if torch.cuda.is_available() else -1
        model_name = "cardiffnlp/twitter-roberta-base-sentiment-latest"
        nlp_pipe = pipeline(
            "sentiment-analysis",
            model=model_name,
            tokenizer=model_name,
            device=device,
            truncation=True,
            max_length=512,
            batch_size=32
        )
        use_transformer = True
    except Exception:
        use_transformer = False

    for series in text_series_iter:
        texts = series.fillna("").astype(str).tolist()
        if use_transformer and nlp_pipe is not None:
            truncated = [t[:1500] if len(t) > 1500 else t for t in texts]
            preds = nlp_pipe(truncated)
            labels, scores = [], []
            for p in preds:
                raw_lbl = p["label"].upper()
                conf = float(p["score"])
                if "NEG" in raw_lbl:
                    labels.append("NEGATIVE")
                    scores.append(round(-conf, 4))
                elif "POS" in raw_lbl:
                    labels.append("POSITIVE")
                    scores.append(round(conf, 4))
                else:
                    labels.append("NEUTRAL")
                    scores.append(0.0)
            yield pd.DataFrame({"sentiment": labels, "sentiment_score": scores})
        else:
            labels, scores = [], []
            for t in texts:
                lbl, sc = score_lexicon_sentiment(t)
                labels.append(lbl)
                scores.append(sc)
            yield pd.DataFrame({"sentiment": labels, "sentiment_score": scores})
