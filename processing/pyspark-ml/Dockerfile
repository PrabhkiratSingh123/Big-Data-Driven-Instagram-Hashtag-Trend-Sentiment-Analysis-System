FROM bitnami/spark:3.5

USER root

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment defaults
ENV KAFKA_BOOTSTRAP_SERVERS=localhost:9092
ENV KAFKA_TOPIC=instagram-posts
ENV MONGO_URI=mongodb://host.docker.internal:27017
ENV MONGO_DB=instagram_analytics
ENV MODEL_DIR=/app/model/sentiment_pipeline
ENV CHECKPOINT_DIR=/tmp/spark-checkpoints/sentiment
ENV PYTHONUNBUFFERED=1

USER 1001

CMD ["spark-submit", \
     "--master", "spark://spark-master:7077", \
     "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.mongodb.spark:mongo-spark-connector_2.12:10.2.1", \
     "/app/stream_processor.py"]
