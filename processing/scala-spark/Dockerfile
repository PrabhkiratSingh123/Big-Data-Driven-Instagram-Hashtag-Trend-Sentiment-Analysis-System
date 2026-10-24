FROM eclipse-temurin:17-jdk as builder

# Install SBT
RUN apt-get update && apt-get install -y curl gnupg2 && \
    echo "deb https://repo.scala-sbt.org/scalasbt/debian all main" | tee /etc/apt/sources.list.d/sbt.list && \
    curl -sL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x99E82A75642AC823" | apt-key add && \
    apt-get update && apt-get install -y sbt && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy build files first for layer caching
COPY build.sbt .
COPY project/ project/

# Download dependencies (cached layer)
RUN sbt update

# Copy source code and build
COPY src/ src/
RUN sbt assembly

# ---- Runtime stage ----
FROM bitnami/spark:3.5

USER root

# Copy the fat JAR
COPY --from=builder /build/target/scala-2.12/instagram-spark-analytics.jar /opt/spark-apps/

# Set environment defaults
ENV KAFKA_BOOTSTRAP_SERVERS=localhost:9092
ENV KAFKA_TOPIC=instagram-posts
ENV MONGO_URI=mongodb://host.docker.internal:27017
ENV MONGO_DB=instagram_analytics
ENV CHECKPOINT_DIR=/tmp/spark-checkpoints

USER 1001

ENTRYPOINT ["spark-submit", \
  "--master", "spark://spark-master:7077", \
  "--packages", "org.mongodb.spark:mongo-spark-connector_2.12:10.2.1", \
  "--class", "com.instagram.analytics.HashtagTrendProcessor", \
  "/opt/spark-apps/instagram-spark-analytics.jar"]
