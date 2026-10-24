"""
SocialTrendML — Spark ML Sentiment Analysis Engine
Uses PySpark MLlib pipeline: Tokenizer → StopWordsRemover → HashingTF → IDF → NaiveBayes
Trains on labeled demo data and provides batch inference.

When Spark is unavailable, falls back to VADER sentiment analysis.
"""

import os
import re
import logging
import shutil
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PySpark MLlib Pipeline
# ---------------------------------------------------------------------------

SPARK_MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "spark_sentiment_pipeline")


def _get_or_create_spark(app_name: str = "SocialTrendML-Sentiment"):
    """Create a local SparkSession."""
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder
        .appName(app_name)
        .master(os.getenv("SPARK_MASTER", "local[*]"))
        .config("spark.driver.memory", "2g")
        .config("spark.sql.shuffle.partitions", "4")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def build_training_data() -> list[dict]:
    """
    Generate labeled training data for the Spark ML pipeline.
    Uses curated examples with clear sentiment signals.
    This is SAMPLE / DEMO data — clearly labeled as such.
    """
    positive = [
        "Absolutely loving this incredible day",
        "Best decision I ever made feeling so grateful and blessed",
        "Life is so beautiful when you appreciate the little things",
        "Finally achieved my goal hard work really does pay off",
        "Surrounded by the most amazing people thankful beyond words",
        "Woke up feeling inspired and ready to conquer the world",
        "Such a wonderful experience highly recommend to everyone",
        "New personal record progress over perfection every single day",
        "The sunset tonight was absolutely magical pure bliss",
        "So proud of how far I have come this year keep going",
        "This place is everything I dreamed of and more paradise found",
        "Celebrating small wins because they lead to big victories",
        "My heart is so full right now grateful for every moment",
        "Dream big work hard stay focused it is all paying off",
        "Incredible energy at this event what an unforgettable night",
        "Found my happy place never want to leave here",
        "Amazing results exceeded all expectations truly outstanding",
        "Feeling blessed and fortunate for this wonderful opportunity",
        "The team did an incredible job proud of everyone involved",
        "What a beautiful morning perfect start to a productive day",
        "Thrilled to announce this exciting new project launch",
        "Wonderful community support makes all the difference",
        "Exceeded our targets this quarter fantastic achievement",
        "Love how this technology makes everything so much easier",
        "Great innovation that solves real problems impressive work",
    ]
    negative = [
        "Really disappointed with how things turned out today",
        "This was honestly a waste of time and money would not recommend",
        "Feeling overwhelmed and exhausted need a break from everything",
        "The quality has really gone downhill lately so frustrating",
        "Having one of those terrible days where nothing goes right",
        "Worst experience ever completely overrated and overpriced",
        "Struggling with motivation lately feeling stuck and lost",
        "The traffic and crowds ruined what should have been a good day",
        "Another broken promise trust is so hard to rebuild",
        "This product completely failed after just one week of use",
        "Terrible customer service experience never going back there",
        "Feeling so burnt out when does the grind actually end",
        "Extremely frustrated with the lack of progress here",
        "The whole system crashed again this is unacceptable",
        "Wasted hours trying to fix this terrible software",
        "So disappointed in the results nothing works as promised",
        "Horrible experience from start to finish avoid this place",
        "The project failed due to poor planning and execution",
        "Cannot believe how badly this was handled total disaster",
        "Stressed and anxious about the upcoming deadline pressure",
        "The service keeps getting worse nothing ever improves",
        "Regret spending money on this complete waste of resources",
        "Angry about the misleading advertising false promises",
        "The bugs in this app make it completely unusable",
        "Lost all my data because of their terrible infrastructure",
    ]
    neutral = [
        "Just another day in the neighborhood",
        "New post thoughts let me know in the comments below",
        "Here is what I have been working on lately work in progress",
        "Quick update from today session more details coming soon",
        "Monday vibes back to the routine after the weekend",
        "Trying something different today we will see how it goes",
        "Behind the scenes look at the process",
        "Just sharing some photos from the other day nothing special",
        "Working on some new things stay tuned for updates",
        "Coffee and emails kind of morning the usual grind",
        "Checking out this new place downtown first impressions so far",
        "Documenting the journey one post at a time",
        "Interesting perspective on things what do you all think",
        "Quick recap of the week some good some bad mostly average",
        "Just passing through caught this random scene on my way",
        "Today schedule looks pretty standard meetings and work",
        "Reviewing the latest data nothing unusual to report",
        "The weather is mild today typical for this time of year",
        "Reading through the documentation for the new release",
        "Setting up the environment for the next phase of testing",
        "Comparing different approaches to solve this problem",
        "Attended the weekly standup discussed ongoing items",
        "Looking at the metrics for last month standard numbers",
        "Updated the configuration files for the deployment",
        "Ran the benchmark tests results are within expected range",
    ]

    data = []
    for text in positive:
        data.append({"text": text, "label": 2.0})  # 2 = positive
    for text in negative:
        data.append({"text": text, "label": 0.0})  # 0 = negative
    for text in neutral:
        data.append({"text": text, "label": 1.0})  # 1 = neutral

    return data


LABEL_MAP = {0.0: "negative", 1.0: "neutral", 2.0: "positive"}
REVERSE_LABEL_MAP = {"negative": 0.0, "neutral": 1.0, "positive": 2.0}


def train_spark_model(force_retrain: bool = False) -> str:
    """
    Train a Spark ML sentiment classification pipeline and save to disk.

    Pipeline: RegexTokenizer → StopWordsRemover → CountVectorizer → IDF → LogisticRegression

    Returns:
        Path to the saved model directory.
    """
    from pyspark.ml import Pipeline
    from pyspark.ml.classification import LogisticRegression
    from pyspark.ml.feature import (
        RegexTokenizer,
        StopWordsRemover,
        CountVectorizer,
        IDF,
    )
    from pyspark.ml.evaluation import MulticlassClassificationEvaluator

    if os.path.exists(SPARK_MODEL_DIR) and not force_retrain:
        logger.info(f"Spark model already exists at {SPARK_MODEL_DIR}. Use force_retrain=True to retrain.")
        return SPARK_MODEL_DIR

    logger.info("Training Spark ML sentiment pipeline...")
    spark = _get_or_create_spark()

    # Build training DataFrame
    training_data = build_training_data()
    df = spark.createDataFrame(training_data)

    # ML Pipeline stages
    tokenizer = RegexTokenizer(
        inputCol="text", outputCol="words", pattern="\\W", minTokenLength=2
    )
    remover = StopWordsRemover(inputCol="words", outputCol="filtered")
    cv = CountVectorizer(inputCol="filtered", outputCol="raw_features", vocabSize=5000, minDF=1.0)
    idf = IDF(inputCol="raw_features", outputCol="features", minDocFreq=1)
    lr = LogisticRegression(
        featuresCol="features",
        labelCol="label",
        maxIter=100,
        regParam=0.01,
        elasticNetParam=0.0,
        family="multinomial",
    )

    pipeline = Pipeline(stages=[tokenizer, remover, cv, idf, lr])

    # Train/test split
    train_df, test_df = df.randomSplit([0.8, 0.2], seed=42)

    # Fit
    model = pipeline.fit(train_df)

    # Evaluate
    predictions = model.transform(test_df)
    evaluator = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="accuracy"
    )
    accuracy = evaluator.evaluate(predictions)
    logger.info(f"Spark ML model accuracy: {accuracy:.2%}")

    f1_evaluator = MulticlassClassificationEvaluator(
        labelCol="label", predictionCol="prediction", metricName="f1"
    )
    f1 = f1_evaluator.evaluate(predictions)
    logger.info(f"Spark ML model F1 score: {f1:.2%}")

    # Save model
    if os.path.exists(SPARK_MODEL_DIR):
        shutil.rmtree(SPARK_MODEL_DIR)

    model.write().overwrite().save(SPARK_MODEL_DIR)
    logger.info(f"Spark ML model saved to {SPARK_MODEL_DIR}")

    return SPARK_MODEL_DIR


def load_spark_model():
    """Load the trained Spark ML pipeline model from disk."""
    from pyspark.ml import PipelineModel

    if not os.path.exists(SPARK_MODEL_DIR):
        logger.info("No saved model found — training now...")
        train_spark_model()

    model = PipelineModel.load(SPARK_MODEL_DIR)
    logger.info("Spark ML model loaded successfully")
    return model


class SparkSentimentAnalyzer:
    """
    Spark ML-based sentiment analyzer.
    Uses a trained PySpark MLlib pipeline for batch classification.

    Limitations:
    - Model is trained on English text only.
    - Trained on curated demo examples — not production-grade NLP.
    - Requires a running Spark context.
    - Sentiment scores are model predictions, not objective truth.
    """

    def __init__(self):
        self._spark = None
        self._model = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy-load Spark and model."""
        if not self._initialized:
            try:
                self._spark = _get_or_create_spark()
                self._model = load_spark_model()
                self._initialized = True
                logger.info("SparkSentimentAnalyzer initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Spark ML: {e}")
                raise

    def analyze_batch(self, texts: list[dict]) -> list[dict]:
        """
        Analyze a batch of texts for sentiment using Spark ML.

        Args:
            texts: List of dicts with at least 'post_id' and 'caption' keys.

        Returns:
            List of sentiment result dicts.
        """
        self._ensure_initialized()

        if not texts:
            return []

        # Build DataFrame
        rows = []
        for t in texts:
            caption = t.get("caption", "") or ""
            cleaned = clean_caption(caption)
            rows.append({
                "post_id": t.get("post_id", ""),
                "original_caption": caption,
                "text": cleaned if cleaned else "empty",
                "source_hashtag": t.get("source_hashtag", ""),
            })

        df = self._spark.createDataFrame(rows)

        # Predict
        predictions = self._model.transform(df)

        # Collect results
        results = []
        for row in predictions.select(
            "post_id", "original_caption", "prediction", "probability", "source_hashtag"
        ).collect():
            sentiment_label = LABEL_MAP.get(row["prediction"], "neutral")
            prob_vector = row["probability"].toArray()
            confidence = float(max(prob_vector)) if prob_vector is not None else 0.0

            results.append({
                "post_id": row["post_id"],
                "caption": row["original_caption"],
                "sentiment": sentiment_label,
                "confidence": round(confidence, 4),
                "keywords": extract_keywords(row["original_caption"]),
                "source_hashtag": row["source_hashtag"],
                "analyzed_at": datetime.now(timezone.utc),
                "model": "spark_ml_lr",
            })

        logger.info(f"Spark ML analyzed {len(results)} posts")
        return results

    def analyze_single(self, text: str, post_id: str = "") -> dict:
        """Analyze a single text."""
        results = self.analyze_batch([{"post_id": post_id, "caption": text}])
        return results[0] if results else {"sentiment": "neutral", "confidence": 0.0}


# ---------------------------------------------------------------------------
# VADER Fallback (when Spark is not available)
# ---------------------------------------------------------------------------

class VaderFallbackAnalyzer:
    """
    VADER-based sentiment analyzer as a fallback when Spark ML is unavailable.
    Uses the NLTK VADER lexicon — rule-based, no training needed.

    Limitations:
    - English-only.
    - Rule-based, less accurate than trained ML models.
    - Does not capture context or sarcasm well.
    """

    def __init__(self):
        self._analyzer = None

    def _ensure_initialized(self):
        if self._analyzer is None:
            try:
                import nltk
                nltk.download("vader_lexicon", quiet=True)
                from nltk.sentiment.vader import SentimentIntensityAnalyzer
                self._analyzer = SentimentIntensityAnalyzer()
                logger.info("VADER fallback analyzer initialized")
            except ImportError:
                logger.error("nltk not installed. Install with: pip install nltk")
                raise

    def analyze_batch(self, texts: list[dict]) -> list[dict]:
        """Analyze batch using VADER."""
        self._ensure_initialized()

        results = []
        for t in texts:
            caption = t.get("caption", "") or ""
            cleaned = clean_caption(caption)

            if not cleaned:
                results.append({
                    "post_id": t.get("post_id", ""),
                    "caption": caption,
                    "sentiment": "neutral",
                    "confidence": 0.5,
                    "keywords": [],
                    "source_hashtag": t.get("source_hashtag", ""),
                    "analyzed_at": datetime.now(timezone.utc),
                    "model": "vader_fallback",
                })
                continue

            scores = self._analyzer.polarity_scores(cleaned)
            compound = scores["compound"]

            if compound >= 0.05:
                sentiment = "positive"
                confidence = min(1.0, (compound + 1) / 2)
            elif compound <= -0.05:
                sentiment = "negative"
                confidence = min(1.0, (-compound + 1) / 2)
            else:
                sentiment = "neutral"
                confidence = 1.0 - abs(compound)

            results.append({
                "post_id": t.get("post_id", ""),
                "caption": caption,
                "sentiment": sentiment,
                "confidence": round(confidence, 4),
                "keywords": extract_keywords(caption),
                "source_hashtag": t.get("source_hashtag", ""),
                "analyzed_at": datetime.now(timezone.utc),
                "model": "vader_fallback",
            })

        return results

    def analyze_single(self, text: str, post_id: str = "") -> dict:
        results = self.analyze_batch([{"post_id": post_id, "caption": text}])
        return results[0] if results else {"sentiment": "neutral", "confidence": 0.0}


# ---------------------------------------------------------------------------
# Shared Utilities
# ---------------------------------------------------------------------------

def clean_caption(text: str) -> str:
    """Clean an Instagram caption for NLP processing."""
    if not text:
        return ""
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove mentions
    text = re.sub(r"@\w+", "", text)
    # Remove hashtags (keep the word part for analysis)
    text = re.sub(r"#(\w+)", r"\1", text)
    # Remove emojis and special characters but keep basic punctuation
    text = re.sub(r"[^\w\s.,!?'-]", "", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_keywords(text: str, top_n: int = 10) -> list[str]:
    """Extract meaningful keywords from text."""
    if not text:
        return []

    cleaned = clean_caption(text).lower()
    # Simple stopwords list
    stopwords = {
        "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of",
        "and", "or", "but", "not", "with", "this", "that", "was", "are",
        "be", "has", "have", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "just", "so", "than",
        "very", "too", "also", "been", "being", "from", "they", "them",
        "their", "there", "here", "when", "where", "how", "what", "which",
        "who", "whom", "why", "all", "each", "every", "both", "few",
        "more", "most", "some", "any", "no", "nor", "only", "own",
        "same", "such", "into", "over", "after", "before", "between",
        "out", "up", "down", "about", "my", "your", "his", "her",
        "its", "our", "we", "you", "he", "she", "me", "him", "us",
        "i", "im", "ive", "dont", "doesnt", "didnt", "wont", "cant",
    }

    words = re.findall(r"\b[a-z]{3,}\b", cleaned)
    keywords = [w for w in words if w not in stopwords]

    # Count frequencies
    freq: dict[str, int] = {}
    for w in keywords:
        freq[w] = freq.get(w, 0) + 1

    # Return top N by frequency
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:top_n]]


def extract_hashtags_from_caption(text: str) -> list[str]:
    """Extract hashtags from caption."""
    if not text:
        return []
    return [tag.lower() for tag in re.findall(r"#(\w+)", text)]


# ---------------------------------------------------------------------------
# Unified Analyzer (tries Spark ML first, falls back to VADER)
# ---------------------------------------------------------------------------

_analyzer_instance = None


def get_sentiment_analyzer():
    """Get the best available sentiment analyzer (Spark ML preferred, VADER fallback)."""
    global _analyzer_instance
    if _analyzer_instance is not None:
        return _analyzer_instance

    try:
        analyzer = SparkSentimentAnalyzer()
        analyzer._ensure_initialized()
        _analyzer_instance = analyzer
        logger.info("Using Spark ML sentiment analyzer")
        return _analyzer_instance
    except Exception as e:
        logger.warning(f"Spark ML unavailable ({e}), falling back to VADER")

    try:
        analyzer = VaderFallbackAnalyzer()
        analyzer._ensure_initialized()
        _analyzer_instance = analyzer
        logger.info("Using VADER fallback sentiment analyzer")
        return _analyzer_instance
    except Exception as e:
        logger.error(f"VADER also unavailable: {e}")
        raise RuntimeError("No sentiment analyzer available. Install pyspark or nltk.")


# ---------------------------------------------------------------------------
# Trend Scoring
# ---------------------------------------------------------------------------

def calculate_trend_score(
    current_count: int,
    previous_count: int,
    avg_sentiment: float = 0.0,
    hours_span: float = 24.0,
) -> float:
    """
    Calculate a transparent trend score for a hashtag.

    Formula:
        trend_score = growth_rate * volume_factor * sentiment_boost

    - growth_rate: (current - previous) / max(previous, 1) — how fast it's growing
    - volume_factor: log2(current + 1) — rewards higher volume but with diminishing returns
    - sentiment_boost: 1.0 + (avg_sentiment * 0.2) — slight boost for positive sentiment

    Args:
        current_count: Posts in the current period
        previous_count: Posts in the previous period
        avg_sentiment: Average sentiment score (-1 to 1)
        hours_span: Number of hours in the period

    Returns:
        Trend score (higher = more trending)
    """
    import math

    if current_count == 0:
        return 0.0

    # Growth rate
    growth_rate = (current_count - previous_count) / max(previous_count, 1)

    # Volume factor (log scale)
    volume_factor = math.log2(current_count + 1)

    # Sentiment boost (mild, ±20%)
    sentiment_boost = 1.0 + (avg_sentiment * 0.2)

    # Velocity (posts per hour)
    velocity = current_count / max(hours_span, 1)

    score = (1.0 + growth_rate) * volume_factor * sentiment_boost * (1.0 + velocity * 0.1)
    return round(max(0.0, score), 4)
