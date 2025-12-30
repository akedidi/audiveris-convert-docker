FROM python:3.11-slim

# Java runtime pour Audiveris
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless curl unzip \
  && rm -rf /var/lib/apt/lists/*

# Télécharge Audiveris (exemple version; change si besoin)
# Les binaires sont publiés dans les "assets" des releases. :contentReference[oaicite:6]{index=6}
ARG AUDIVERIS_VERSION=5.9.0
WORKDIR /opt/audiveris
RUN curl -L -o audiveris.zip \
    https://github.com/Audiveris/audiveris/releases/download/${AUDIVERIS_VERSION}/Audiveris-${AUDIVERIS_VERSION}-linux-x86_64.zip \
 && unzip audiveris.zip \
 && rm audiveris.zip \
 && find . -name "*.jar" -maxdepth 3 -print

# Selon l’archive, le jar peut être dans un sous-dossier; on crée un lien stable
RUN JAR_PATH="$(find /opt/audiveris -name 'audiveris*.jar' | head -n 1)" \
 && ln -sf "$JAR_PATH" /opt/audiveris/audiveris.jar

# App
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

# Render route le trafic vers le port PORT :contentReference[oaicite:7]{index=7}
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
