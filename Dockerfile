FROM python:3.11-slim

# Outils + dépendances runtime (headless) + OCR optionnel
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates unzip \
    fontconfig libfreetype6 \
    libx11-6 libxext6 libxi6 libxrender1 libxtst6 \
    tesseract-ocr tesseract-ocr-eng \
  && rm -rf /var/lib/apt/lists/*

# Choisis une release + flavor qui existent (ubuntu22.04 ou ubuntu24.04)
ARG AUDIVERIS_VERSION=5.7.0
ARG AUDIVERIS_LINUX_FLAVOR=ubuntu22.04

WORKDIR /tmp

# Télécharge le .deb, extrait dans /opt/audiveris, puis crée:
# - /opt/audiveris/audiveris.jar (lien stable)
# - /opt/audiveris/java          (lien vers le java inclus dans l’installer)
RUN curl -fL -o audiveris.deb \
    https://github.com/Audiveris/audiveris/releases/download/${AUDIVERIS_VERSION}/Audiveris-${AUDIVERIS_VERSION}-${AUDIVERIS_LINUX_FLAVOR}-x86_64.deb \
 && mkdir -p /opt/audiveris \
 && dpkg-deb -x audiveris.deb /opt/audiveris \
 && rm audiveris.deb \
 && JAR_PATH="$(find /opt/audiveris -type f -name 'audiveris*.jar' | head -n 1)" \
 && echo "Audiveris jar: $JAR_PATH" \
 && ln -sf "$JAR_PATH" /opt/audiveris/audiveris.jar \
 && JAVA_PATH="$(find /opt/audiveris -type f -path '*/bin/java' | head -n 1)" \
 && echo "Bundled java: $JAVA_PATH" \
 && ln -sf "$JAVA_PATH" /opt/audiveris/java

ENV AUDIVERIS_JAR=/opt/audiveris/audiveris.jar
ENV AUDIVERIS_JAVA=/opt/audiveris/java

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
