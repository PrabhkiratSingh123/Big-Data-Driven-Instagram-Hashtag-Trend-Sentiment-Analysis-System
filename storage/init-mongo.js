// =============================================================
// MongoDB Initialization Script
// Creates collections, indexes, and validation for
// Instagram Hashtag Trend & Sentiment Analysis System
// =============================================================

print("🚀 Initializing Instagram Analytics database...");

db = db.getSiblingDB("instagram_analytics");

// --- Create Collections with Schema Validation ---

db.createCollection("raw_posts", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["post_id", "username", "caption", "hashtags", "timestamp"],
      properties: {
        post_id: { bsonType: "string", description: "Unique post identifier" },
        username: { bsonType: "string", description: "Instagram username" },
        caption: { bsonType: "string", description: "Post caption text" },
        hashtags: {
          bsonType: "array",
          items: { bsonType: "string" },
          description: "Array of hashtags",
        },
        timestamp: { bsonType: "date", description: "Post creation timestamp" },
        media_type: { bsonType: "string", description: "Type: IMAGE, VIDEO, CAROUSEL" },
        likes_count: { bsonType: "int", description: "Number of likes" },
        comments_count: { bsonType: "int", description: "Number of comments" },
        media_url: { bsonType: "string", description: "URL of the media" },
        ingested_at: { bsonType: "date", description: "When the post was ingested" },
      },
    },
  },
});

db.createCollection("hashtag_trends", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["hashtag", "window_start", "window_end", "count"],
      properties: {
        hashtag: { bsonType: "string" },
        window_start: { bsonType: "date" },
        window_end: { bsonType: "date" },
        window_duration_min: { bsonType: "int" },
        count: { bsonType: "int" },
        velocity: { bsonType: "double", description: "Rate of change in usage" },
        co_occurring: {
          bsonType: "array",
          items: { bsonType: "string" },
          description: "Frequently co-occurring hashtags",
        },
        updated_at: { bsonType: "date" },
      },
    },
  },
});

db.createCollection("engagement_metrics", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["hashtag"],
      properties: {
        hashtag: { bsonType: "string" },
        total_posts: { bsonType: "int" },
        avg_likes: { bsonType: "double" },
        avg_comments: { bsonType: "double" },
        engagement_rate: { bsonType: "double" },
        max_likes: { bsonType: "int" },
        max_comments: { bsonType: "int" },
        peak_hour: { bsonType: "int", description: "Hour of day with peak engagement (0-23)" },
        updated_at: { bsonType: "date" },
      },
    },
  },
});

db.createCollection("sentiment_scores", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["post_id", "sentiment_label", "sentiment_score"],
      properties: {
        post_id: { bsonType: "string" },
        caption: { bsonType: "string" },
        sentiment_label: {
          bsonType: "string",
          enum: ["positive", "neutral", "negative"],
        },
        sentiment_score: { bsonType: "double" },
        confidence: { bsonType: "double" },
        hashtags: { bsonType: "array", items: { bsonType: "string" } },
        timestamp: { bsonType: "date" },
        processed_at: { bsonType: "date" },
      },
    },
  },
});

// --- Create Indexes ---

print("📑 Creating indexes...");

// raw_posts indexes
db.raw_posts.createIndex({ post_id: 1 }, { unique: true });
db.raw_posts.createIndex({ timestamp: -1, hashtags: 1 });
db.raw_posts.createIndex({ username: 1 });
db.raw_posts.createIndex({ ingested_at: -1 });

// hashtag_trends indexes
db.hashtag_trends.createIndex(
  { hashtag: 1, window_start: -1, window_duration_min: 1 },
  { unique: true }
);
db.hashtag_trends.createIndex({ window_start: -1 });
db.hashtag_trends.createIndex({ count: -1 });

// engagement_metrics indexes
db.engagement_metrics.createIndex({ hashtag: 1 }, { unique: true });
db.engagement_metrics.createIndex({ engagement_rate: -1 });

// sentiment_scores indexes
db.sentiment_scores.createIndex({ post_id: 1 }, { unique: true });
db.sentiment_scores.createIndex({ timestamp: -1, sentiment_label: 1 });
db.sentiment_scores.createIndex({ sentiment_label: 1 });

print("✅ Instagram Analytics database initialized successfully!");
print("   Collections: raw_posts, hashtag_trends, engagement_metrics, sentiment_scores");
