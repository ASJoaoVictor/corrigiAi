FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WORK_DIR=/tmp/corrigiai \
    OCR_MODEL_DIR=/app/ocr-models

WORKDIR /app

# OpenMP is required by the CPU numerical/OCR wheels; no GUI libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install CPU wheels first to avoid bringing CUDA into a CPU-only server.
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

COPY . .
RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid appuser --create-home appuser \
    && mkdir -p /app/data /app/instance /app/ocr-models /tmp/corrigiai \
    && chown -R appuser:appuser /app/data /app/instance /app/ocr-models /tmp/corrigiai \
    && chmod 700 /app/data /tmp/corrigiai

USER appuser
# Cached in the image: requests never download models or load OCR at startup.
RUN python scripts/prepare_ocr.py

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "180", "--graceful-timeout", "30", "--error-logfile", "-", "app:create_app()"]
