name := "instagram-spark-analytics"

version := "1.0.0"

scalaVersion := "2.12.18"

val sparkVersion = "3.5.0"

libraryDependencies ++= Seq(
  // Spark Core & SQL
  "org.apache.spark" %% "spark-core" % sparkVersion % "provided",
  "org.apache.spark" %% "spark-sql"  % sparkVersion % "provided",

  // Spark Streaming + Kafka Integration
  "org.apache.spark" %% "spark-sql-kafka-0-10" % sparkVersion,

  // MongoDB Spark Connector
  "org.mongodb.spark" %% "mongo-spark-connector" % "10.2.1",

  // JSON parsing
  "com.google.code.gson" % "gson" % "2.10.1",

  // Logging
  "org.slf4j" % "slf4j-api" % "2.0.9",
  "ch.qos.logback" % "logback-classic" % "1.4.14"
)

// Assembly plugin settings for fat JAR
assembly / assemblyMergeStrategy := {
  case PathList("META-INF", xs @ _*) =>
    xs match {
      case "MANIFEST.MF" :: Nil => MergeStrategy.discard
      case "services" :: _      => MergeStrategy.concat
      case _                    => MergeStrategy.discard
    }
  case "reference.conf" => MergeStrategy.concat
  case x if x.endsWith(".proto") => MergeStrategy.first
  case _ => MergeStrategy.first
}

assembly / assemblyJarName := "instagram-spark-analytics.jar"

// Compiler options
scalacOptions ++= Seq(
  "-deprecation",
  "-encoding", "utf-8",
  "-feature",
  "-unchecked"
)
