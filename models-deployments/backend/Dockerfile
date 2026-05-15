FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ONNX_MODEL_DIR=/app/.cache/onnx

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Bake ONNX model into image — no runtime download, no token needed
RUN python -c " \
from huggingface_hub import hf_hub_download; \
import os; \
os.makedirs('/app/.cache/onnx', exist_ok=True); \
hf_hub_download(repo_id='optimum/all-MiniLM-L6-v2', filename='model.onnx', local_dir='/app/.cache/onnx'); \
hf_hub_download(repo_id='optimum/all-MiniLM-L6-v2', filename='tokenizer.json', local_dir='/app/.cache/onnx'); \
print('ONNX model baked in successfully') \
"

COPY . .

EXPOSE 8000
EXPOSE 50051

CMD ["gunicorn", "app:app", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "120"]