# ---- Builder stage: compile/install everything that needs build tools ----
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --user numpy==1.26.4 \
    && pip install --no-cache-dir --user -r requirements.txt

# ---- Runtime stage: slim image, only what's needed to run ----
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ONNX_MODEL_DIR=/app/.cache/onnx

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libjpeg62-turbo \
    libopenjp2-7 \
    && rm -rf /var/lib/apt/lists/*

# Create appuser BEFORE copying, so we can chown directly into place
RUN useradd --create-home --shell /bin/bash appuser

# Copy installed packages into appuser's own home instead of /root
COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/home/appuser/.local/lib/python3.11/site-packages

COPY --chown=appuser:appuser download_model.py .
COPY --chown=appuser:appuser . .

RUN chown -R appuser:appuser /app

USER appuser

# Download spaCy model AFTER switching to appuser, into the runtime stage
# so it lands in the same site-packages tree that PYTHONPATH points to
RUN python -m spacy download en_core_web_sm

RUN python download_model.py

EXPOSE 8000
EXPOSE 50051

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["gunicorn", "main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "1", \
     "--timeout", "300", "--graceful-timeout", "30"]