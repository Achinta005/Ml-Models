FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ONNX_MODEL_DIR=/app/.cache/onnx

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-eng \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY download_model.py .
RUN python download_model.py

COPY . .

EXPOSE 8000
EXPOSE 50051

CMD ["gunicorn", "app:app", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "120"]