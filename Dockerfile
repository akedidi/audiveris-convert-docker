FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates unzip bash \
    fontconfig libfreetype6 \
    libx11-6 libxext6 libxi6 libxrender1 libxtst6 \
    tesseract-ocr tesseract-ocr-eng \
  && rm -rf /var/lib/apt/lists/*

ARG AUDIVERIS_VERSION=5.7.0
ARG AUDIVERIS_LINUX_FLAVOR=ubuntu22.04

WORKDIR /tmp
RUN curl -fL -o audiveris.deb \
      https://github.com/Audiveris/audiveris/releases/download/${AUDIVERIS_VERSION}/Audiveris-${AUDIVERIS_VERSION}-${AUDIVERIS_LINUX_FLAVOR}-x86_64.deb \
 && mkdir -p /opt/audiveris \
 && dpkg-deb -x audiveris.deb /opt/audiveris \
 && rm audiveris.deb \
 && JAVA_PATH="$(find /opt/audiveris -type f -path '*/bin/java' | head -n 1)" \
 && echo "Bundled java: $JAVA_PATH" \
 && ln -sf "$JAVA_PATH" /opt/audiveris/java

# Crée le wrapper en 2 RUN pour éviter les soucis de parsing
RUN cat > /opt/audiveris/run-audiveris.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

JAVA="/opt/audiveris/java"

# 1) Si un launcher officiel existe, on l’utilise
LAUNCHER="$(find /opt/audiveris -type f \( -path '*/usr/bin/audiveris' -o -path '*/usr/bin/Audiveris' -o -name 'audiveris' -o -name 'Audiveris' \) 2>/dev/null | head -n 1 || true)"
if [[ -n "${LAUNCHER}" ]]; then
  chmod +x "${LAUNCHER}" || true
  export JAVA_HOME="$(cd "$(dirname "$JAVA")/.." && pwd)"
  export PATH="$(dirname "$JAVA"):${PATH}"
  exec "${LAUNCHER}" "$@"
fi

# 2) Fallback : reconstruire un classpath avec tous les jars
CP="$(find /opt/audiveris -type f -name '*.jar' 2>/dev/null | paste -sd ':' -)"
if [[ -z "${CP}" ]]; then
  echo "ERROR: No JARs found under /opt/audiveris" >&2
  exit 2
fi

export JAVA_HOME="$(cd "$(dirname "$JAVA")/.." && pwd)"
export PATH="$(dirname "$JAVA"):${PATH}"

exec "${JAVA}" -cp "${CP}" Audiveris "$@"
SH

RUN chmod +x /opt/audiveris/run-audiveris.sh

ENV AUDIVERIS_CMD=/opt/audiveris/run-audiveris.sh

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
