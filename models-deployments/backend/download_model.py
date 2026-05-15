from huggingface_hub import hf_hub_download
import os

os.makedirs("/app/.cache/onnx", exist_ok=True)

hf_hub_download(repo_id="optimum/all-MiniLM-L6-v2", filename="model.onnx", local_dir="/app/.cache/onnx")
hf_hub_download(repo_id="optimum/all-MiniLM-L6-v2", filename="tokenizer.json", local_dir="/app/.cache/onnx")

print("ONNX model baked in successfully")