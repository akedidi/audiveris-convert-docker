FROM python:3.11-slim

# Java runtime pour Audiveris (Fix A: Java 21 sur Debian trixie)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless curl unzip \
  && rm -rf /var/lib/apt/lists/*

# Télécharger Audiveris (adapte la version si besoin)
ARG AUDIVERIS_VERSION=5.9.0
WORKDIR /opt/audiveris

# Télécharge le zip Linux depuis les releases Audiveris, dézippe, puis crée un lien stable /opt/audiveris/audiveris.jar
RUN curl -L -o audiveris.zip \
    https://github.com/Audiveris/audiveris/releases/download/${AUDIVERIS_VERSION}/Audiveris-${AUDIVERIS_VERSION}-linux-x86_64.zip \
 && unzip audiveris.zip \
 && rm audiveris.zip \
 && JAR_PATH="$(find /opt/audiveris -name 'audiveris*.jar' | head -n 1)" \
 && ln -sf "$JAR_PATH" /opt/audiveris/audiveris.jar

# App (FastAPI)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

# Render attend un serveur HTTP sur $PORT
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
