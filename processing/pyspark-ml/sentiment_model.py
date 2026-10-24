"""
Sentiment Analysis Model — Spark MLlib Pipeline
Trains a text classification pipeline for sentiment analysis:
  Tokenizer → StopWordsRemover → HashingTF → IDF → NaiveBayes

Can train on:
  1. Generated synthetic labeled data (for development)
  2. Custom labeled dataset (CSV with 'text' and 'label' columns)

The trained model is saved to disk and loaded by stream_processor.py
for real-time inference on Kafka streams.
"""

import os
import sys
import logging
import random

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, IntegerType
from pyspark.ml import Pipeline, PipelineModel
from pyspark.ml.feature import (
    Tokenizer,
    StopWordsRemover,
    HashingTF,
    IDF,
    StringIndexer,
    IndexToString,
)
from pyspark.ml.classification import NaiveBayes
from pyspark.ml.evaluation import MulticlassClassificationEvaluator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("sentiment_model")

# Model save path
MODEL_DIR = os.getenv(
    "MODEL_DIR",
    os.path.join(os.path.dirname(__file__), "model", "sentiment_pipeline"),
)

# =====================================================================
# Synthetic Training Data Generator
# =====================================================================

POSITIVE_SAMPLES = [
    "Absolutely loving this incredible day the vibes are unmatched",
    "Best decision I ever made feeling so grateful and blessed",
    "Can't stop smiling life is so beautiful",
    "This view just took my breath away nature is truly amazing",
    "Finally achieved my goal hard work really does pay off",
    "Surrounded by the most amazing people thankful beyond words",
    "Woke up feeling inspired and ready to conquer the world",
    "This made my entire week so happy right now",
    "Living my best life and I wouldn't change a thing",
    "Such a wonderful experience highly recommend to everyone",
    "New personal record progress over perfection every single day",
    "The sunset tonight was absolutely magical pure bliss",
    "So proud of how far I've come this year keep going",
    "This place is everything I dreamed of and more paradise found",
    "Celebrating small wins because they lead to big victories",
    "My heart is so full right now grateful for every moment",
    "Dream big work hard stay focused it's all paying off",
    "Incredible energy at this event what an unforgettable night",
    "So excited about this amazing opportunity thank you all",
    "This is the most beautiful thing I have ever seen wow",
    "Great vibes great people great memories nothing but love",
    "Perfect day for an adventure loving every minute of this",
    "Just received the best news ever feeling on top of the world",
    "Everything about this is perfect absolutely stunning quality",
    "What an amazing journey grateful for every step of the way",
    "Feeling blessed and grateful for all the love and support",
    "This exceeded all my expectations truly remarkable experience",
    "Happiest day of my life everything is falling into place",
    "Such a positive and uplifting experience loved every second",
    "Incredible talent on display truly inspired by this performance",
]

NEGATIVE_SAMPLES = [
    "Really disappointed with how things turned out today",
    "This was honestly a waste of time and money would not recommend",
    "Feeling overwhelmed and exhausted need a break from everything",
    "The quality has really gone downhill lately so frustrating",
    "Can't believe this happened again when will things change",
    "Having one of those terrible days where nothing goes right",
    "So tired of the fake positivity let's be real for once",
    "Worst experience ever completely overrated and overpriced",
    "Struggling with motivation lately feeling stuck and lost",
    "The traffic and crowds ruined what should have been a good day",
    "Another broken promise trust is so hard to rebuild",
    "This product completely failed after just one week of use",
    "Missing how things used to be change isn't always good",
    "Terrible customer service experience never going back there",
    "Feeling so burnt out when does the grind actually end",
    "Very poor quality nothing like what was advertised terrible",
    "Extremely annoyed with the lack of communication disappointing",
    "This ruined my day completely unacceptable behavior and service",
    "Horrible experience from start to finish avoid at all costs",
    "So frustrated with the constant delays and broken promises",
    "Nothing works as expected total waste of time and effort",
    "The worst purchase I have ever made deeply regret this",
    "Disgusted by the poor quality and lack of accountability",
    "Everything went wrong today feeling angry and let down",
    "Completely dissatisfied with the outcome demanded a refund",
    "Such a letdown expected so much more than this garbage",
    "Painfully slow service and rude staff never returning here",
    "Broken on arrival terrible packaging and zero quality control",
    "This place has gone way downhill used to be great now awful",
    "Scam alert do not fall for this terrible misleading product",
]

NEUTRAL_SAMPLES = [
    "Just another day in the neighborhood",
    "New post thoughts let me know in the comments below",
    "Here's what I've been working on lately work in progress",
    "Quick update from today's session more details coming soon",
    "Monday vibes back to the routine after the weekend",
    "Trying something different today we'll see how it goes",
    "Behind the scenes look at the process",
    "Just sharing some photos from the other day nothing special",
    "Working on some new things stay tuned for updates",
    "Coffee and emails kind of morning the usual grind",
    "Checking out this new place downtown first impressions so far",
    "Documenting the journey one post at a time",
    "Interesting perspective on things what do you all think",
    "Quick recap of the week some good some bad mostly average",
    "Just passing through caught this random scene on my way",
    "Not sure what to think about this yet needs more thought",
    "Regular day at work nothing too exciting to report today",
    "Testing out the new feature seems to work as intended",
    "Here are the details for the event tomorrow everyone welcome",
    "Wednesday update everything is on track for the deadline",
    "Simple meal for tonight nothing fancy just the basics",
    "Standard commute this morning same route same traffic same view",
    "Finished reading the article had some interesting points overall",
    "Weather is okay today not great not terrible just normal",
    "Completed the task moving on to the next thing on the list",
    "Attended the meeting discussed the usual topics and agenda items",
    "Here is the information you requested all details included below",
    "Ordered the same thing as usual it was fine as expected",
    "Took a walk around the park saw some birds and trees",
    "Watched the movie it was alright nothing groundbreaking really",
]


def generate_training_data(spark: SparkSession, samples_per_class: int = 500):
    """
    Generate synthetic labeled training data by augmenting template sentences.
    Returns a Spark DataFrame with 'text' and 'label' columns.
    """
    logger.info(f"Generating {samples_per_class * 3} synthetic training samples...")

    data = []

    for _ in range(samples_per_class):
        # Positive
        text = random.choice(POSITIVE_SAMPLES)
        # Add slight variations
        if random.random() < 0.3:
            text = text + " " + random.choice(["amazing", "wonderful", "love it", "perfect", "great"])
        data.append((text, "positive"))

        # Negative
        text = random.choice(NEGATIVE_SAMPLES)
        if random.random() < 0.3:
            text = text + " " + random.choice(["terrible", "awful", "hate it", "worst", "bad"])
        data.append((text, "negative"))

        # Neutral
        text = random.choice(NEUTRAL_SAMPLES)
        if random.random() < 0.3:
            text = text + " " + random.choice(["okay", "fine", "whatever", "normal", "average"])
        data.append((text, "neutral"))

    schema = StructType([
        StructField("text", StringType(), False),
        StructField("label", StringType(), False),
    ])

    return spark.createDataFrame(data, schema)


def build_pipeline():
    """
    Build the Spark MLlib sentiment analysis pipeline:
    Tokenizer → StopWordsRemover → HashingTF → IDF → NaiveBayes
    """
    # Stage 1: Convert text to lowercase tokens
    tokenizer = Tokenizer(inputCol="text", outputCol="words")

    # Stage 2: Remove stop words
    remover = StopWordsRemover(inputCol="words", outputCol="filtered_words")

    # Stage 3: Term frequency with hashing
    hashing_tf = HashingTF(
        inputCol="filtered_words",
        outputCol="raw_features",
        numFeatures=10000,
    )

    # Stage 4: Inverse document frequency
    idf = IDF(inputCol="raw_features", outputCol="features", minDocFreq=2)

    # Stage 5: Convert string labels to numeric indices
    label_indexer = StringIndexer(
        inputCol="label",
        outputCol="label_index",
        handleInvalid="keep",
    )

    # Stage 6: Naive Bayes classifier
    nb = NaiveBayes(
        featuresCol="features",
        labelCol="label_index",
        predictionCol="prediction",
        probabilityCol="probability",
        modelType="multinomial",
        smoothing=1.0,
    )

    # Stage 7: Convert numeric predictions back to labels
    label_converter = IndexToString(
        inputCol="prediction",
        outputCol="predicted_label",
        labels=["positive", "neutral", "negative"],  # Will be overridden by fitted indexer
    )

    pipeline = Pipeline(stages=[
        tokenizer, remover, hashing_tf, idf,
        label_indexer, nb, label_converter
    ])

    return pipeline


def train_model(
    spark: SparkSession,
    training_data=None,
    model_dir: str = None,
):
    """
    Train the sentiment analysis model.

    Args:
        spark: SparkSession
        training_data: Optional DataFrame with 'text' and 'label' columns.
                       If None, generates synthetic training data.
        model_dir: Directory to save the trained model.

    Returns:
        Fitted PipelineModel
    """
    model_dir = model_dir or MODEL_DIR

    if training_data is None:
        training_data = generate_training_data(spark, samples_per_class=800)

    logger.info(f"Training data: {training_data.count()} samples")
    training_data.groupBy("label").count().show()

    # Split data
    train_df, test_df = training_data.randomSplit([0.8, 0.2], seed=42)
    logger.info(f"Train: {train_df.count()}, Test: {test_df.count()}")

    # Build and train pipeline
    pipeline = build_pipeline()
    logger.info("Training sentiment model...")
    model = pipeline.fit(train_df)

    # Evaluate
    predictions = model.transform(test_df)
    evaluator = MulticlassClassificationEvaluator(
        labelCol="label_index",
        predictionCol="prediction",
    )

    accuracy = evaluator.evaluate(predictions, {evaluator.metricName: "accuracy"})
    f1 = evaluator.evaluate(predictions, {evaluator.metricName: "f1"})
    precision = evaluator.evaluate(predictions, {evaluator.metricName: "weightedPrecision"})
    recall = evaluator.evaluate(predictions, {evaluator.metricName: "weightedRecall"})

    logger.info("=" * 50)
    logger.info("📊 Model Evaluation Results:")
    logger.info(f"   Accuracy:  {accuracy:.4f}")
    logger.info(f"   F1 Score:  {f1:.4f}")
    logger.info(f"   Precision: {precision:.4f}")
    logger.info(f"   Recall:    {recall:.4f}")
    logger.info("=" * 50)

    # Show sample predictions
    logger.info("\nSample predictions:")
    predictions.select("text", "label", "predicted_label", "probability").show(10, truncate=50)

    # Save model
    logger.info(f"Saving model to {model_dir}...")
    model.write().overwrite().save(model_dir)
    logger.info(f"✅ Model saved to {model_dir}")

    return model


def load_model(model_dir: str = None) -> PipelineModel:
    """Load a previously trained model."""
    model_dir = model_dir or MODEL_DIR
    logger.info(f"Loading model from {model_dir}...")
    return PipelineModel.load(model_dir)


if __name__ == "__main__":
    spark = SparkSession.builder \
        .appName("SentimentModelTraining") \
        .master("local[*]") \
        .config("spark.driver.memory", "2g") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    logger.info("🚀 Starting Sentiment Model Training")
    model = train_model(spark)
    logger.info("🎉 Training complete!")

    spark.stop()
