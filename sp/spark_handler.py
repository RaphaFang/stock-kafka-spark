from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, sum as spark_sum, avg, last, lit, to_timestamp, current_timestamp
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, BooleanType


class SparkHandler:
    def __init__(self):
        self.spark = SparkSession.builder \
            .master("local[*]") \
            .appName("SparkApp") \
            .config("spark.executor.instances", "1") \
            .config("spark.executor.cores", "2") \
            .getOrCreate()
            # 先設置1個executor，並且他有兩個core
            # .config("spark.jars", "/opt/spark/jars/spark-sql-kafka-0-10_2.12-3.1.2.jar") \

        self.schema = StructType([
            StructField("symbol", StringType(), True),
            StructField("type", StringType(), True),
            StructField("exchange", StringType(), True),
            StructField("market", StringType(), True),
            StructField("price", DoubleType(), True),
            StructField("size", IntegerType(), True),
            StructField("bid", DoubleType(), True),
            StructField("ask", DoubleType(), True),
            StructField("volume", IntegerType(), True),
            StructField("isContinuous", BooleanType(), True),
            StructField("time", StringType(), True), 
            StructField("serial", StringType(), True),
            StructField("id", StringType(), True),
            StructField("channel", StringType(), True)
        ])

        # self.latest_data = {}

    def process_data(self):
        kafka_df = self.spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", "kafka:9092") \
            .option("subscribe", "raw_data") \
            .option("startingOffsets", "latest") \
            .load()
        

        def process_batch(df, epoch_id):
            if df.rdd.isEmpty():
                print(f"Batch {epoch_id} is empty, skipping processing.")
                return

            df = df.selectExpr("CAST(value AS STRING) as json_data") \
                .select(from_json(col("json_data"), self.schema).alias("data")) \
                .select("data.*")
            
            df = df.withColumn("time", to_timestamp(col("time") / 1000000))

            df.printSchema()

# 讀取出資料，並且建立計算基本資料，並且使用withWatermark然下面沒辦法用append
            # .withWatermark("time", "1 minute")
            windowed_df = df.groupBy(
                window(col("time"), "1 second"),
                col("symbol")
            ).agg(
                spark_sum(col("price") * col("size")).alias("price_time_size"),  
                spark_sum("size").alias("size_per_sec"),
                # last("price", ignorenulls=True).alias("last_price"),
                last("volume", ignorenulls=True).alias("volume_till_now"),
                last("time", ignorenulls=True).alias("last_data_time"),
                # last("serial", ignorenulls=True).alias("last_serial"),
                last("isContinuous", ignorenulls=True).alias("isContinuous")
            )
# 計算每秒資料，並且調整欄位名稱，準備輸出
            result_df = windowed_df.withColumn(
                "vwap_price_per_sec", col("price_time_size") / col("size_per_sec")
            ).select(
                "symbol",
                "vwap_price_per_sec",
                "volume_till_now",
                "size_per_sec",
                "last_data_time",
                # "last_serial as serial",  # 這個架構好像不支持這樣重新命名的操作
                # col("last_isClose").alias("isClose"),  # 不然就是要這樣命名
                "isContinuous",
                "window.start", 
                "window.end",
                current_timestamp().alias("current_time") 
            )

            result_df.selectExpr(
                "CAST(symbol AS STRING) AS key",
                "to_json(struct(*)) AS value"
            ).write \
                .format("kafka") \
                .option("kafka.bootstrap.servers", "kafka:9092") \
                .option("topic", "processed_data") \
                .save()
            # ).writeStream \
            #     .outputMode("append") \
            #     .format("kafka") \
            #     .option("kafka.bootstrap.servers", "kafka:9092") \
            #     .option("topic", "processed_data") \
            #     .trigger(processingTime='1 seconds') \
            #     .option("checkpointLocation", "/app/tmp/spark-checkpoints") \
            #     .start()
            #     # 這邊先設定成一秒推送一次，看看效能
            
        query = kafka_df.writeStream \
            .foreachBatch(process_batch) \
            .trigger(processingTime='1 second') \
            .option("checkpointLocation", "/app/tmp/spark-checkpoints") \
            .start()
        query.awaitTermination()

    def stop(self):
        self.spark.stop()
        # # 补充缺失的数据
        # for symbol in df.select("symbol").distinct().collect():
        #     symbol_str = symbol["symbol"]
        #     if symbol_str not in self.latest_data:
        #         self.latest_data[symbol_str] = None

        #     # 如果当前窗口内没有数据，使用最近的数据填补
        #     if self.latest_data[symbol_str] is None or df.filter(df.symbol == symbol_str).count() == 0:
        #         windowed_df = windowed_df.withColumn(
        #             "price", last("price", ignorenulls=True).over(W.partitionBy("symbol").orderBy("time"))
        #         )
        #         windowed_df = windowed_df.withColumn("sum_volume", lit(0))

        #     # 更新最近的数据
        #     self.latest_data[symbol_str] = windowed_df.filter(windowed_df.symbol == symbol_str).select("last_price").collect()[0]["last_price"]