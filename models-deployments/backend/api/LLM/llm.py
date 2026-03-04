from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import List, Optional
import httpx
import time
import os

from config.logging_config import logger

router = APIRouter()

# ── Config ────────────────────────────────────────────────────
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:latest")
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_MODEL_ID = os.getenv("HF_MODEL_ID", "meta-llama/Meta-Llama-3.1-8B-Instruct")
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL_ID}"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


# ── Schemas ───────────────────────────────────────────────────
class Message(BaseModel):
    role: str = Field(..., example="user")
    content: str = Field(..., example="Hello!")


class LLMRequest(BaseModel):
    messages: List[Message]
    max_tokens: int = Field(512, ge=1, le=4096)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float = Field(0.95, ge=0.0, le=1.0)


class LLMResponse(BaseModel):
    response: str
    model: str
    mode: str  # "local" or "cloud"
    duration_ms: float


# ── Helper: Check if Ollama is running locally ────────────────
async def is_ollama_running() -> bool:
    """Ping Ollama — returns True if local Ollama is up."""
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


# ── Helper: Call local Ollama ─────────────────────────────────
async def call_ollama(messages: list, max_tokens: int, temperature: float) -> str:
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            },
        )

        # Debug: print raw response if error
        if response.status_code != 200:
            raise HTTPException(
                status_code=500,
                detail=f"Ollama error {response.status_code}: {response.text}",
            )

        return response.json()["message"]["content"]


# ── Helper: Call HuggingFace Inference API ────────────────────
async def call_hf_api(messages: list, max_tokens: int, temperature: float) -> str:
    # Convert messages to a single prompt string
    prompt = ""
    for m in messages:
        role = m["role"]
        content = m["content"]
        if role == "system":
            prompt += f"System: {content}\n"
        elif role == "user":
            prompt += f"User: {content}\n"
        elif role == "assistant":
            prompt += f"Assistant: {content}\n"
    prompt += "Assistant:"

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            HF_API_URL,
            headers=headers,
            json={
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "return_full_text": False,
                    "stop": ["User:", "System:"],
                },
            },
        )

        result = response.json()

        # Handle HF API errors
        if isinstance(result, dict) and "error" in result:
            raise HTTPException(
                status_code=503, detail=f"HF API error: {result['error']}"
            )

        if isinstance(result, list):
            return result[0].get("generated_text", "").strip()

        raise HTTPException(status_code=500, detail=f"Unexpected HF response: {result}")


# ── Routes ────────────────────────────────────────────────────


@router.get("/health")
async def llm_health():
    """
    Check LLM status.
    Shows which mode will be used: local Ollama or HF cloud API.
    """
    ollama_up = await is_ollama_running()

    if ollama_up:
        # Get list of available local models
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{OLLAMA_URL}/api/tags")
                models = [m["name"] for m in r.json().get("models", [])]
        except Exception:
            models = []

        return {
            "status": "ok",
            "mode": "local",
            "ollama_url": OLLAMA_URL,
            "ollama_model": OLLAMA_MODEL,
            "available_models": models,
            "environment": ENVIRONMENT,
        }
    else:
        return {
            "status": "ok",
            "mode": "cloud",
            "hf_api_url": HF_API_URL,
            "hf_token_set": bool(HF_TOKEN),
            "environment": ENVIRONMENT,
        }


@router.post("/chat", response_model=LLMResponse)
async def llm_chat(request: LLMRequest, http_request: Request):
    """
    Chat with Llama 3.1.

    Auto-detects mode:
    - LOCAL:  Ollama running on localhost → uses it (fast, private)
    - CLOUD:  Ollama not found → falls back to HF Inference API
    """
    request_id = getattr(http_request.state, "request_id", "unknown")
    start = time.time()
    messages = [m.dict() for m in request.messages]

    # ── Decide mode ───────────────────────────────────────────
    ollama_up = await is_ollama_running()
    mode = "local" if ollama_up else "cloud"

    logger.info(
        f"LLM chat [{mode}]",
        extra={"request_id": request_id, "mode": mode, "messages": len(messages)},
    )

    # ── Call the right backend ────────────────────────────────
    try:
        if mode == "local":
            # ✅ Local Ollama (development)
            logger.info("Using local Ollama", extra={"request_id": request_id})
            reply = await call_ollama(
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
            model_name = OLLAMA_MODEL

        else:
            # ☁️ HuggingFace Inference API (production)
            logger.info("Using HF Inference API", extra={"request_id": request_id})

            if not HF_TOKEN:
                raise HTTPException(
                    status_code=503,
                    detail="HF_TOKEN not set. Add it to environment variables.",
                )

            reply = await call_hf_api(
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
            model_name = HF_MODEL_ID

        duration_ms = round((time.time() - start) * 1000, 2)

        logger.info(
            f"LLM chat done [{mode}]",
            extra={"request_id": request_id, "duration_ms": duration_ms, "mode": mode},
        )

        return LLMResponse(
            response=reply, model=model_name, mode=mode, duration_ms=duration_ms
        )

    except HTTPException:
        raise
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503, detail="Cannot connect to Ollama. Run: ollama serve"
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504, detail="LLM request timed out. Try reducing max_tokens."
        )
    except Exception as e:
        logger.error(f"LLM error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/docs",
    summary="LLM API Documentation",
    include_in_schema=False,  # hides from swagger, it's its own page
)
async def llm_docs():
    from fastapi.responses import HTMLResponse

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>LLM API Docs</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; }
            .header { background: linear-gradient(135deg, #1e3a5f, #0f172a); padding: 40px; border-bottom: 1px solid #1e40af; }
            .header h1 { font-size: 2rem; color: #60a5fa; }
            .header p  { color: #94a3b8; margin-top: 8px; }
            .badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: bold; margin-left: 12px; }
            .badge.get  { background: #064e3b; color: #34d399; }
            .badge.post { background: #1e3a8a; color: #60a5fa; }
            .container  { max-width: 900px; margin: 40px auto; padding: 0 24px; }
            .section    { margin-bottom: 40px; }
            .section h2 { font-size: 1.1rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 16px; }
            .endpoint   { background: #1e293b; border: 1px solid #334155; border-radius: 12px; margin-bottom: 16px; overflow: hidden; }
            .endpoint-header { display: flex; align-items: center; padding: 16px 20px; cursor: pointer; gap: 12px; }
            .endpoint-header:hover { background: #263548; }
            .method { font-weight: bold; font-size: 0.85rem; padding: 4px 10px; border-radius: 6px; min-width: 52px; text-align: center; }
            .method.GET  { background: #064e3b; color: #34d399; }
            .method.POST { background: #1e3a8a; color: #60a5fa; }
            .path  { font-family: monospace; font-size: 1rem; color: #f1f5f9; }
            .desc  { color: #94a3b8; font-size: 0.875rem; margin-left: auto; }
            .endpoint-body { padding: 20px; border-top: 1px solid #334155; display: none; }
            .endpoint-body.open { display: block; }
            .label { font-size: 0.8rem; color: #60a5fa; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin: 16px 0 8px; }
            pre  { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 16px; font-size: 0.85rem; overflow-x: auto; color: #a5f3fc; line-height: 1.6; }
            table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
            th   { text-align: left; padding: 10px 12px; background: #0f172a; color: #60a5fa; font-weight: 600; border-bottom: 1px solid #334155; }
            td   { padding: 10px 12px; border-bottom: 1px solid #1e293b; color: #cbd5e1; vertical-align: top; }
            td code { background: #0f172a; padding: 2px 6px; border-radius: 4px; color: #a5f3fc; font-size: 0.8rem; }
            .required { color: #f87171; font-size: 0.75rem; }
            .optional { color: #94a3b8; font-size: 0.75rem; }
            .mode-box { display: flex; gap: 12px; margin-top: 8px; }
            .mode { flex: 1; background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 14px; }
            .mode h4 { color: #34d399; margin-bottom: 6px; }
            .mode.cloud h4 { color: #60a5fa; }
            .mode p { color: #94a3b8; font-size: 0.85rem; }
            .try-btn { margin-top: 16px; padding: 10px 20px; background: #1e40af; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 0.875rem; }
            .try-btn:hover { background: #2563eb; }
            .response-box { margin-top: 12px; background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 16px; display: none; }
            .response-box.show { display: block; }
            textarea { width: 100%; background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; color: #a5f3fc; font-family: monospace; font-size: 0.85rem; resize: vertical; margin-top: 8px; }
            .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 6px; }
            .tag.local { background: #064e3b; color: #34d399; }
            .tag.cloud { background: #1e3a8a; color: #60a5fa; }
        </style>
    </head>
    <body>

    <div class="header">
        <h1>⚡ LLM API <span class="badge get">v1.0.0</span></h1>
        <p>Llama 3.1 — Auto switches between local Ollama and HuggingFace cloud</p>
        <div style="margin-top:16px; display:flex; gap:16px;">
            <div style="background:#0f172a; padding:10px 16px; border-radius:8px; font-family:monospace; font-size:0.85rem; color:#94a3b8;">
                Base URL: <span style="color:#60a5fa">http://localhost:8000</span>
            </div>
            <div style="background:#0f172a; padding:10px 16px; border-radius:8px; font-size:0.85rem; color:#94a3b8;">
                <span class="tag local">🖥 Local</span> Ollama on localhost:11434
                <span class="tag cloud" style="margin-left:8px">☁ Cloud</span> HuggingFace Inference API
            </div>
        </div>
    </div>

    <div class="container">

        <!-- Health -->
        <div class="section">
            <h2>Endpoints</h2>

            <div class="endpoint">
                <div class="endpoint-header" onclick="toggle('health')">
                    <span class="method GET">GET</span>
                    <span class="path">/api/llm/health</span>
                    <span class="desc">Check LLM status & active mode</span>
                </div>
                <div class="endpoint-body" id="health">
                    <div class="label">Description</div>
                    <p style="color:#94a3b8; font-size:0.9rem;">Returns current LLM mode (local or cloud), available models, and connection status.</p>

                    <div class="label">Example Response</div>
                    <pre>{
  "status": "ok",
  "mode": "local",
  "ollama_url": "http://localhost:11434",
  "ollama_model": "llama3.1:latest",
  "available_models": ["llama3.1:latest"],
  "environment": "development"
}</pre>
                    <button class="try-btn" onclick="tryHealth()">▶ Try it</button>
                    <div class="response-box" id="health-res"></div>
                </div>
            </div>

            <!-- Chat -->
            <div class="endpoint">
                <div class="endpoint-header" onclick="toggle('chat')">
                    <span class="method POST">POST</span>
                    <span class="path">/api/llm/chat</span>
                    <span class="desc">Chat with Llama 3.1</span>
                </div>
                <div class="endpoint-body" id="chat">

                    <div class="mode-box">
                        <div class="mode">
                            <h4>🖥 Local Mode</h4>
                            <p>Ollama detected on localhost → uses your local Llama 3.1 model</p>
                        </div>
                        <div class="mode cloud">
                            <h4>☁ Cloud Mode</h4>
                            <p>No Ollama → falls back to HuggingFace Inference API automatically</p>
                        </div>
                    </div>

                    <div class="label">Request Body</div>
                    <table>
                        <tr><th>Field</th><th>Type</th><th>Required</th><th>Default</th><th>Description</th></tr>
                        <tr><td><code>messages</code></td><td>array</td><td><span class="required">required</span></td><td>—</td><td>Conversation history</td></tr>
                        <tr><td><code>messages[].role</code></td><td>string</td><td><span class="required">required</span></td><td>—</td><td><code>system</code> / <code>user</code> / <code>assistant</code></td></tr>
                        <tr><td><code>messages[].content</code></td><td>string</td><td><span class="required">required</span></td><td>—</td><td>Message text</td></tr>
                        <tr><td><code>max_tokens</code></td><td>int</td><td><span class="optional">optional</span></td><td>512</td><td>Max response length (1–4096)</td></tr>
                        <tr><td><code>temperature</code></td><td>float</td><td><span class="optional">optional</span></td><td>0.7</td><td>Creativity level (0.0–2.0)</td></tr>
                        <tr><td><code>top_p</code></td><td>float</td><td><span class="optional">optional</span></td><td>0.95</td><td>Nucleus sampling (0.0–1.0)</td></tr>
                    </table>

                    <div class="label">Example Request</div>
                    <pre>{
  "messages": [
    {"role": "system",    "content": "You are a helpful assistant."},
    {"role": "user",      "content": "What is machine learning?"}
  ],
  "max_tokens": 256,
  "temperature": 0.7
}</pre>

                    <div class="label">Example Response</div>
                    <pre>{
  "response": "Machine learning is a branch of AI...",
  "model": "llama3.1:latest",
  "mode": "local",
  "duration_ms": 12456.19
}</pre>

                    <div class="label">Response Fields</div>
                    <table>
                        <tr><th>Field</th><th>Type</th><th>Description</th></tr>
                        <tr><td><code>response</code></td><td>string</td><td>LLM reply text</td></tr>
                        <tr><td><code>model</code></td><td>string</td><td>Model used</td></tr>
                        <tr><td><code>mode</code></td><td>string</td><td><code>local</code> or <code>cloud</code></td></tr>
                        <tr><td><code>duration_ms</code></td><td>float</td><td>Response time in ms</td></tr>
                    </table>

                    <div class="label">Try it</div>
                    <textarea id="chat-body" rows="8">{
  "messages": [
    {"role": "user", "content": "Say hello in one sentence."}
  ],
  "max_tokens": 100,
  "temperature": 0.7
}</textarea>
                    <button class="try-btn" onclick="tryChat()">▶ Send Request</button>
                    <div class="response-box" id="chat-res"></div>
                </div>
            </div>
        </div>

        <!-- Code Examples -->
        <div class="section">
            <h2>Code Examples</h2>
            <div class="endpoint">
                <div class="endpoint-header" onclick="toggle('code')">
                    <span class="method GET" style="background:#4a1d96;color:#c4b5fd">{ }</span>
                    <span class="path">Python / JavaScript</span>
                    <span class="desc">Copy-paste examples</span>
                </div>
                <div class="endpoint-body" id="code">
                    <div class="label">Python</div>
                    <pre>import requests

r = requests.post("http://localhost:8000/api/llm/chat", json={
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user",   "content": "What is machine learning?"}
    ],
    "max_tokens": 256,
    "temperature": 0.7
})
print(r.json()["response"])</pre>

                    <div class="label">JavaScript (fetch)</div>
                    <pre>const res = await fetch("http://localhost:8000/api/llm/chat", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    messages: [
      { role: "user", content: "What is machine learning?" }
    ],
    max_tokens: 256,
    temperature: 0.7
  })
});
const data = await res.json();
console.log(data.response);</pre>

                    <div class="label">cURL</div>
                    <pre>curl -X POST http://localhost:8000/api/llm/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello!"}],"max_tokens":100}'</pre>
                </div>
            </div>
        </div>

    </div>

    <script>
        function toggle(id) {
            const el = document.getElementById(id);
            el.classList.toggle('open');
        }

        async function tryHealth() {
            const box = document.getElementById('health-res');
            box.className = 'response-box show';
            box.style.color = '#94a3b8';
            box.innerHTML = 'Loading...';
            try {
                const r = await fetch('/api/llm/health');
                const data = await r.json();
                box.style.color = '#34d399';
                box.innerHTML = '<pre style="background:none;border:none;color:#34d399">' + JSON.stringify(data, null, 2) + '</pre>';
            } catch(e) {
                box.style.color = '#f87171';
                box.innerHTML = 'Error: ' + e.message;
            }
        }

        async function tryChat() {
            const box  = document.getElementById('chat-res');
            const body = document.getElementById('chat-body').value;
            box.className = 'response-box show';
            box.style.color = '#94a3b8';
            box.innerHTML = 'Sending request... (may take 10-30s)';
            try {
                const r = await fetch('/api/llm/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: body
                });
                const data = await r.json();
                box.style.color = '#60a5fa';
                box.innerHTML = '<pre style="background:none;border:none;color:#60a5fa">' + JSON.stringify(data, null, 2) + '</pre>';
            } catch(e) {
                box.style.color = '#f87171';
                box.innerHTML = 'Error: ' + e.message;
            }
        }
    </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
