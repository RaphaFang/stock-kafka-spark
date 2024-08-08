FROM openjdk:11-jdk-slim

# 為了跑腳本，要安裝這個
# RUN apt-get update && apt-get install -y netcat-openbsd

# ENV DEBIAN_FRONTEND=noninteractive
# ENV TZ=Asia/Taipei

RUN apt-get update && apt-get install -y \
    python3.9 \
    python3-pip \
    wget \
    procps \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*


# RUN apt-get update && apt-get install -y procps openjdk-11-jdk
# 安裝java，
# ENV JAVA_HOME /usr/lib/jvm/java-11-openjdk-amd64
# ENV PATH $JAVA_HOME/bin:$PATH

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 下载并安装Spark和Kafka连接器
RUN wget https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.1.2/spark-sql-kafka-0-10_2.12-3.1.2.jar -P /opt/spark/jars/
RUN wget https://repo1.maven.org/maven2/org/apache/spark/spark-streaming-kafka-0-10_2.12/3.1.2/spark-streaming-kafka-0-10_2.12-3.1.2.jar -P /opt/spark/jars/


COPY . .

# COPY wait.sh /wait.sh
# RUN chmod +x /wait.sh

EXPOSE 8000

# CMD ["python3", "main.py"]
CMD ["spark-submit", "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.1.2", "main.py"]

# "/wait.sh",