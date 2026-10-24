package com.instagram.analytics

import com.mongodb.client.{MongoClients, MongoCollection, MongoDatabase}
import com.mongodb.client.model.{ReplaceOptions, Filters}
import org.bson.Document
import org.apache.spark.sql.{DataFrame, Row}
import java.util.Date

/**
 * MongoWriter
 *
 * Utility object for writing Spark DataFrames to MongoDB.
 * Provides batch upsert capabilities for trend and engagement data.
 * Used as a fallback when the MongoDB Spark Connector's direct write
 * mode doesn't support the desired upsert semantics.
 */
object MongoWriter {

  /**
   * Upsert rows from a DataFrame into a MongoDB collection.
   * Uses the specified key fields to match existing documents.
   *
   * @param df         DataFrame to write
   * @param mongoUri   MongoDB connection URI
   * @param database   Database name
   * @param collection Collection name
   * @param keyFields  Fields to use as the upsert filter
   */
  def upsertBatch(
    df: DataFrame,
    mongoUri: String,
    database: String,
    collection: String,
    keyFields: Seq[String]
  ): Unit = {
    // Process each partition on the executor
    df.foreachPartition { (partition: Iterator[Row]) =>
      val client = MongoClients.create(mongoUri)
      val db: MongoDatabase = client.getDatabase(database)
      val coll: MongoCollection[Document] = db.getCollection(collection)
      val replaceOptions = new ReplaceOptions().upsert(true)

      try {
        partition.foreach { row =>
          val doc = rowToDocument(row)
          doc.put("updated_at", new Date())

          // Build filter from key fields
          val filterDoc = new Document()
          keyFields.foreach { key =>
            if (row.schema.fieldNames.contains(key)) {
              val idx = row.fieldIndex(key)
              if (!row.isNullAt(idx)) {
                filterDoc.put(key, row.get(idx))
              }
            }
          }

          if (!filterDoc.isEmpty) {
            coll.replaceOne(filterDoc, doc, replaceOptions)
          } else {
            coll.insertOne(doc)
          }
        }
      } finally {
        client.close()
      }
    }
  }

  /**
   * Convert a Spark Row to a MongoDB Document.
   */
  private def rowToDocument(row: Row): Document = {
    val doc = new Document()
    row.schema.fields.foreach { field =>
      val idx = row.fieldIndex(field.name)
      if (!row.isNullAt(idx)) {
        val value = row.get(idx) match {
          case ts: java.sql.Timestamp => new Date(ts.getTime)
          case arr: scala.collection.mutable.WrappedArray[_] =>
            val list = new java.util.ArrayList[Any]()
            arr.foreach(list.add)
            list
          case other => other
        }
        doc.put(field.name, value)
      }
    }
    doc
  }

  /**
   * Convenience method to write hashtag trends with proper upsert keys.
   */
  def writeHashtagTrends(df: DataFrame, mongoUri: String, database: String): Unit = {
    upsertBatch(
      df, mongoUri, database,
      collection = "hashtag_trends",
      keyFields = Seq("hashtag", "window_start", "window_duration_min")
    )
  }

  /**
   * Convenience method to write engagement metrics with proper upsert keys.
   */
  def writeEngagementMetrics(df: DataFrame, mongoUri: String, database: String): Unit = {
    upsertBatch(
      df, mongoUri, database,
      collection = "engagement_metrics",
      keyFields = Seq("hashtag")
    )
  }
}
