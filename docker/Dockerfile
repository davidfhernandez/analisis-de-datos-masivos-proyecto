FROM python:3.10-slim

# Instalar Java (requerido para PySpark) y utilidades base
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    procps \
    git \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/default-java
ENV PATH=$PATH:$JAVA_HOME/bin
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python3", "src/join_f1_data.py"]
