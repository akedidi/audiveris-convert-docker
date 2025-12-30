FROM python:3.11-slim

# Java runtime (Fix A: Java 21) + outils + libs headless utiles
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    curl ca-certificates \
    fontconfig libfreetype6 \
    libx11-6 libxext6 libxi6 libxrender1 libxtst6 \
    tesseract-ocr tesseract-ocr-eng \
  && rm -rf /var/lib/apt/lists/*

# Audiveris (version + flavor qui existent)
ARG AUDIVERIS_VERSION=5.6.0
ARG AUDIVERIS_LINUX_FLAVOR=ubuntu22.04

WORKDIR /tmp
RUN curl -fL -o audiveris.deb \
    https://github.com/Audiveris/audiveris/releases/download/${AUDIVERIS_VERSION}/Audiveris-${AUDIVERIS_VERSION}-${AUDIVERIS_LINUX_FLAVOR}-x86_64.deb \
 && mkdir -p /opt/audiveris \
 && dpkg-deb -x audiveris.deb /opt/audiveris \
 && rm audiveris.deb \
 && JAR_PATH="$(find /opt/audiveris -type f -name 'audiveris*.jar' | head -n 1)" \
 && echo "Audiveris jar: $JAR_PATH" \
 && ln -sf "$JAR_PATH" /opt/audiveris/audiveris.jar

# App (FastAPI)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
