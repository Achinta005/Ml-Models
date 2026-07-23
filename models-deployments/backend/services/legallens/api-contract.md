# LegalLens — FastAPI API Contract

> **Base URL:** `http://ai-service:8000`
> **Called by:** NestJS server only (internal network — never exposed to browser directly)
> **Auth:** NestJS passes `X-Internal-Token` header + `X-Org-Id` + `X-User-Role` on every request
> **Data format:** JSON in, JSON out (except export endpoints which return binary)

---

## Table of Contents

1. [POST /analyze](#1-post-analyze)
2. [POST /qa](#2-post-qa)
3. [POST /compare](#3-post-compare)
4. [GET /clauses](#4-get-clauses)
5. [POST /export/redline](#5-post-exportredline)
6. [POST /export/summary](#6-post-exportsummary)
7. [POST /cross-query](#7-post-cross-query)
8. [Shared Types](#shared-types)
9. [Error Format](#error-format)
10. [Pipeline Cheat Sheet](#pipeline-cheat-sheet)

---

## 1. `POST /analyze`

### Purpose

Core risk analysis pipeline. Triggered by a **BullMQ background job** from NestJS — never called directly by the frontend. Downloads the contract from S3, extracts text, segments clauses, classifies risk, generates Claude explanations, and writes all results back to Postgres.

### Request

```http
POST /analyze
Content-Type: application/json
X-Internal-Token: <secret>
X-Org-Id: <org_uuid>
```

```json
{
  "contract_id": "uuid",
  "s3_key": "orgs/org-uuid/contracts/file.pdf",
  "org_id": "uuid",
  "file_name": "vendor-agreement-2025.pdf",
  "mime_type": "application/pdf"
}
```

| Field           | Type              | Required | Description                                                                                        |
| --------------- | ----------------- | -------- | -------------------------------------------------------------------------------------------------- |
| `contract_id` | `string (uuid)` | ✅       | Postgres contract row ID                                                                           |
| `s3_key`      | `string`        | ✅       | S3 object key for the uploaded file                                                                |
| `org_id`      | `string (uuid)` | ✅       | Tenant scoping — all Qdrant vectors tagged with this                                              |
| `file_name`   | `string`        | ✅       | Original filename (for logging)                                                                    |
| `mime_type`   | `string`        | ✅       | `application/pdf` or `application/vnd.openxmlformats-officedocument.wordprocessingml.document` |

### Response `200 OK`

```json
{
  "contract_id": "uuid",
  "status": "done",
  "risk_score": 74,
  "total_clauses": 42,
  "flagged_clauses": 11,
  "risk_breakdown": {
    "low": 20,
    "medium": 11,
    "high": 8,
    "critical": 3
  },
  "processing_time_ms": 18400
}
```

### Pipeline

```
1. Download PDF from S3 (boto3)
       ↓
2. pdfplumber → extract raw text + page number map
       ↓ (if text < 100 chars or extraction fails)
3. Tesseract OCR fallback → pytesseract.image_to_string()
   [AWS Textract as second fallback for complex scans]
       ↓
4. spaCy (en_core_web_trf) → sentence boundary detection
   → split into clause chunks[]
   → attach { start_char, end_char, page_no } to each chunk
       ↓
5. For each clause chunk (batched, batch_size=20):
   ├── OpenAI text-embedding-3-large → 1536-dim vector
   └── Qdrant upsert → collection: "org_{org_id}"
                        payload: { contract_id, clause_index, page_no, text }
       ↓
6. legal-BERT classifier (fine-tuned) → per-clause:
   └── { risk_label: low|medium|high|critical, confidence: float }
       ↓
7. Collect high + critical clauses → batch prompt to Claude API
   prompt: "Explain why this clause is risky in plain English..."
   → { explanation: string } per clause
       ↓
8. Calculate overall risk_score:
   score = (medium×1 + high×3 + critical×5) / total_clauses × 20  [0–100]
       ↓
9. Postgres writes:
   ├── UPDATE contracts SET status='done', risk_score=X WHERE id=contract_id
   └── INSERT INTO clauses (contract_id, text, start_char, end_char,
                            page_no, risk_label, risk_score, explanation)
       ↓
10. Emit to NestJS WebSocket gateway:
    { event: 'analysis.complete', data: { contract_id, risk_score, status } }
```

### Error Responses

| Status  | Code                  | Meaning                                       |
| ------- | --------------------- | --------------------------------------------- |
| `422` | `EXTRACTION_FAILED` | Both pdfplumber and OCR returned empty text   |
| `500` | `CLASSIFIER_ERROR`  | BERT model failed — partial results returned |
| `504` | `LLM_TIMEOUT`       | Claude API did not respond within 25s         |

---

## 2. `POST /qa`

### Purpose

RAG-powered Q&A over a single contract. User types a question in the chat UI → NestJS auth-checks the request → forwards here → FastAPI searches Qdrant for relevant clauses → streams Claude's cited answer back.

### Request

```http
POST /qa
Content-Type: application/json
X-Internal-Token: <secret>
X-Org-Id: <org_uuid>
```

```json
{
  "contract_id": "uuid",
  "question": "What happens if either party wants to terminate early?",
  "conversation_history": [
    { "role": "user", "content": "Who are the parties in this contract?" },
    { "role": "assistant", "content": "The parties are Acme Corp and XYZ Ltd..." }
  ],
  "top_k": 5
}
```

| Field                    | Type              | Required | Default | Description                         |
| ------------------------ | ----------------- | -------- | ------- | ----------------------------------- |
| `contract_id`          | `string (uuid)` | ✅       | —      | Which contract to search            |
| `question`             | `string`        | ✅       | —      | User's natural language question    |
| `conversation_history` | `array`         | ❌       | `[]`  | Prior turns for context window      |
| `top_k`                | `integer`       | ❌       | `5`   | Number of clause chunks to retrieve |

### Response `200 OK`

```json
{
  "answer": "Either party may terminate with 30 days written notice under Clause 14.2...",
  "citations": [
    {
      "clause_id": "uuid",
      "page_no": 7,
      "text": "Either party may terminate this Agreement upon thirty (30) days written notice...",
      "relevance_score": 0.91
    }
  ],
  "found_relevant_clauses": true
}
```

> If no relevant clauses found: `"found_relevant_clauses": false` and `"answer"` explicitly states uncertainty — Claude never hallucinates a clause reference.

### Pipeline

```
1. Receive question string
       ↓
2. text-embedding-3-large → embed question → query vector
       ↓
3. Qdrant similarity search:
   collection: "org_{org_id}"
   filter: { contract_id: <id> }
   top_k: 5
   → returns [{ clause_text, page_no, clause_id, score }]
       ↓
4. If max score < 0.65 threshold:
   → return { found_relevant_clauses: false, answer: "I could not find..." }
       ↓
5. Build Claude prompt:
   system:  "You are a legal analyst. Answer only from the provided clauses.
             Always cite the exact clause. If unsure, say so."
   context: clause_1 [page 7]: "..."
            clause_2 [page 12]: "..."
   history: [prior turns]
   user:    question
       ↓
6. Claude API (streaming) → stream tokens back to NestJS
       ↓
7. Parse final response → extract clause references
       ↓
8. Return { answer, citations[] }
```

---

## 3. `POST /compare`

### Purpose

Template gap analysis. Compares an uploaded contract against a standard template stored in the system. Finds clauses present in template but missing from contract (gaps), and clauses in contract not in template (extras).

### Request

```http
POST /compare
Content-Type: application/json
X-Internal-Token: <secret>
```

```json
{
  "contract_id": "uuid",
  "template_id": "uuid",
  "org_id": "uuid",
  "similarity_threshold": 0.78
}
```

| Field                    | Type              | Required | Default  | Description                          |
| ------------------------ | ----------------- | -------- | -------- | ------------------------------------ |
| `contract_id`          | `string (uuid)` | ✅       | —       | Contract to be compared              |
| `template_id`          | `string (uuid)` | ✅       | —       | Template to compare against          |
| `org_id`               | `string (uuid)` | ✅       | —       | Tenant scope                         |
| `similarity_threshold` | `float`         | ❌       | `0.78` | Cosine similarity cutoff for MATCHED |

### Response `200 OK`

```json
{
  "matched": [
    { "template_clause": "...", "contract_clause": "...", "similarity": 0.92 }
  ],
  "missing": [
    { "clause_text": "Limitation of liability shall not exceed...", "risk_label": "critical" }
  ],
  "extra": [
    { "clause_text": "Contractor retains all IP rights...", "risk_label": "high" }
  ],
  "match_score": 68,
  "summary": "This contract is missing a liability cap clause and an indemnity clause present in the standard template..."
}
```

### Pipeline

```
1. Load contract clause vectors from Qdrant
   (already embedded during /analyze)
       ↓
2. Load template clauses from Postgres
   └── if template not yet embedded:
       → embed all template clauses → upsert to Qdrant
         collection: "template_{template_id}"
       ↓
3. For each template clause:
   └── Qdrant search in contract collection
       → best match score ≥ threshold? → MATCHED
       → score < threshold?             → MISSING (gap)
       ↓
4. For each contract clause:
   └── Qdrant search in template collection
       → no match above threshold?      → EXTRA
       ↓
5. Calculate match_score:
   match_score = (matched / total_template_clauses) × 100
       ↓
6. Claude API → summarize gaps:
   prompt: "Given these missing and extra clauses, summarize the key
            legal gaps in plain English for a non-lawyer."
       ↓
7. Return { matched, missing, extra, match_score, summary }
```

---

## 4. `GET /clauses`

### Purpose

Returns all parsed and classified clauses for a contract. Called when the frontend contract viewer loads — data is already pre-computed from the `/analyze` run so no AI calls happen here.

### Request

```http
GET /clauses?contract_id=<uuid>&risk_filter=high,critical
X-Internal-Token: <secret>
X-Org-Id: <org_uuid>
```

| Query Param     | Type              | Required | Default    | Description                                  |
| --------------- | ----------------- | -------- | ---------- | -------------------------------------------- |
| `contract_id` | `string (uuid)` | ✅       | —         | Which contract                               |
| `risk_filter` | `string (csv)`  | ❌       | all levels | Comma-separated:`low,medium,high,critical` |
| `page`        | `integer`       | ❌       | `1`      | Pagination                                   |
| `page_size`   | `integer`       | ❌       | `50`     | Results per page                             |

### Response `200 OK`

```json
{
  "contract_id": "uuid",
  "total_clauses": 42,
  "clauses": [
    {
      "id": "uuid",
      "text": "Contractor shall indemnify and hold harmless...",
      "start_char": 4821,
      "end_char": 5103,
      "page_no": 4,
      "risk_label": "critical",
      "risk_score": 91,
      "confidence": 0.96,
      "explanation": "This clause places unlimited indemnity obligations on the contractor..."
    }
  ],
  "page": 1,
  "page_size": 50
}
```

### Pipeline

```
1. Read from Postgres:
   SELECT * FROM clauses WHERE contract_id = ? [AND risk_label IN (?)]
   ORDER BY risk_score DESC
       ↓
2. Paginate results
       ↓
3. Return structured clause list
```

*(No AI call — pure DB read)*

---

## 5. `POST /export/redline`

### Purpose

Generates a Word DOCX with tracked-change redline suggestions. High/critical clauses get red highlights with Claude-generated replacement suggestions as revision comments. Returns binary file.

### Request

```http
POST /export/redline
Content-Type: application/json
X-Internal-Token: <secret>
```

```json
{
  "contract_id": "uuid",
  "org_id": "uuid",
  "include_suggestions": true
}
```

| Field                   | Type              | Required | Default  | Description                                 |
| ----------------------- | ----------------- | -------- | -------- | ------------------------------------------- |
| `contract_id`         | `string (uuid)` | ✅       | —       | Contract to export                          |
| `include_suggestions` | `boolean`       | ❌       | `true` | Whether to call Claude for replacement text |

### Response `200 OK`

```
Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document
Content-Disposition: attachment; filename="redline_<contract_id>.docx"

<binary DOCX stream>
```

### Pipeline

```
1. Fetch original PDF from S3 (boto3)
       ↓
2. Fetch all clauses + risk labels from Postgres
       ↓
3. If include_suggestions=true:
   └── For each high/critical clause:
       Claude API prompt: "Suggest a safer replacement for this clause.
                           Output only the replacement text."
       → { suggestion: string } per clause
       ↓
4. python-docx → rebuild document paragraph by paragraph:
   ├── low clauses    → plain text, no markup
   ├── medium clauses → yellow highlight + comment: "Review recommended"
   ├── high clauses   → orange highlight + tracked change comment
   │                    + Claude suggestion text
   └── critical clauses → red highlight + tracked change comment
                          + Claude suggestion text + ⚠️ flag
       ↓
5. Save DOCX to temp file → stream binary back to NestJS
       ↓
6. NestJS streams response directly to browser
```

---

## 6. `POST /export/summary`

### Purpose

Generates a clean, executive-friendly 1-page PDF risk summary. Designed for client-role users who need a deliverable without seeing the full legal details.

### Request

```http
POST /export/summary
Content-Type: application/json
X-Internal-Token: <secret>
```

```json
{
  "contract_id": "uuid",
  "org_id": "uuid",
  "include_executive_summary": true
}
```

### Response `200 OK`

```
Content-Type: application/pdf
Content-Disposition: attachment; filename="summary_<contract_id>.pdf"

<binary PDF stream>
```

### Pipeline

```
1. Fetch contract metadata from Postgres:
   { file_name, risk_score, risk_breakdown, created_at }
       ↓
2. Fetch top 10 high/critical clauses from Postgres
       ↓
3. If include_executive_summary=true:
   Claude API → generate 2–3 paragraph plain-English summary:
   prompt: "Summarize the key risks in this contract for a business executive.
             Avoid legal jargon."
       ↓
4. WeasyPrint / reportlab → build PDF layout:
   ├── Header: contract name, date, org name
   ├── Risk score gauge (0–100 visual)
   ├── Risk breakdown bar chart (low/medium/high/critical counts)
   ├── Executive summary paragraphs (from Claude)
   └── Flagged clauses table:
       { clause snippet | risk level | plain-English explanation }
       ↓
5. Return PDF binary stream
```

---

## 7. `POST /cross-query`

### Purpose

RAG Q&A that searches across **all contracts in a matter** (a matter = a grouped set of contracts). Used for queries like *"Compare termination clauses across all Q3 contracts"*.

### Request

```http
POST /cross-query
Content-Type: application/json
X-Internal-Token: <secret>
X-Org-Id: <org_uuid>
```

```json
{
  "matter_id": "uuid",
  "contract_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "question": "Compare the termination clauses across all these contracts",
  "top_k_per_contract": 3
}
```

| Field                  | Type              | Required | Default | Description                      |
| ---------------------- | ----------------- | -------- | ------- | -------------------------------- |
| `matter_id`          | `string (uuid)` | ✅       | —      | Matter/group ID (for logging)    |
| `contract_ids`       | `string[]`      | ✅       | —      | All contract IDs in the matter   |
| `question`           | `string`        | ✅       | —      | The cross-document question      |
| `top_k_per_contract` | `integer`       | ❌       | `3`   | Clauses to retrieve per contract |

### Response `200 OK`

```json
{
  "answer": "Contract A has a 30-day termination notice period, while Contract B allows immediate termination for cause...",
  "citations": [
    {
      "contract_id": "uuid-1",
      "contract_name": "vendor-agreement-a.pdf",
      "clause_id": "uuid",
      "page_no": 7,
      "text": "Either party may terminate with 30 days notice..."
    },
    {
      "contract_id": "uuid-2",
      "contract_name": "vendor-agreement-b.pdf",
      "clause_id": "uuid",
      "page_no": 5,
      "text": "Immediate termination permitted upon material breach..."
    }
  ],
  "contracts_searched": 3,
  "found_relevant_clauses": true
}
```

### Pipeline

```
1. Receive question + contract_ids[]
       ↓
2. text-embedding-3-large → embed question → query vector
       ↓
3. For each contract_id (parallel async):
   └── Qdrant similarity search:
       collection: "org_{org_id}"
       filter: { contract_id: <id> }
       top_k: top_k_per_contract
       → returns top matching clauses tagged with contract_id
       ↓
4. Merge all results → sort by relevance score → deduplicate
       ↓
5. Build Claude prompt:
   system:  "You are a legal analyst comparing multiple contracts.
             Always cite which contract each point comes from."
   context: [CONTRACT A - vendor-agreement-a.pdf]
             clause [page 7]: "..."
            [CONTRACT B - vendor-agreement-b.pdf]
             clause [page 5]: "..."
   user:    question
       ↓
6. Claude API → response with per-contract citations
       ↓
7. Parse citations → match back to contract_ids
       ↓
8. Return { answer, citations[] }
```

---

## Shared Types

```typescript
// Risk label enum
type RiskLabel = "low" | "medium" | "high" | "critical"

// Clause object returned by multiple endpoints
interface Clause {
  id: string           // uuid
  text: string         // raw clause text
  start_char: number   // char offset in full document
  end_char: number
  page_no: number
  risk_label: RiskLabel
  risk_score: number   // 0–100
  confidence: number   // 0–1, model confidence
  explanation: string  // Claude-generated plain-English explanation
}

// Citation returned by QA endpoints
interface Citation {
  clause_id: string
  contract_id: string
  contract_name?: string   // only in /cross-query
  page_no: number
  text: string
  relevance_score: number  // Qdrant cosine similarity
}
```

---

## Error Format

All errors follow this structure:

```json
{
  "error": {
    "code": "EXTRACTION_FAILED",
    "message": "Could not extract text from the uploaded file.",
    "detail": "pdfplumber returned 0 characters; OCR confidence was 12% (threshold: 60%)",
    "contract_id": "uuid"
  }
}
```

### Error Codes Reference

| Code                      | HTTP    | Endpoint                                | Meaning                                                        |
| ------------------------- | ------- | --------------------------------------- | -------------------------------------------------------------- |
| `EXTRACTION_FAILED`     | `422` | `/analyze`                            | Text extraction + OCR both failed                              |
| `CLASSIFIER_ERROR`      | `500` | `/analyze`                            | BERT model crashed — partial results                          |
| `LLM_TIMEOUT`           | `504` | any                                     | Claude API exceeded 25s timeout                                |
| `QDRANT_UNAVAILABLE`    | `503` | `/qa`, `/compare`, `/cross-query` | Vector DB connection failed                                    |
| `CONTRACT_NOT_FOUND`    | `404` | any                                     | `contract_id` not found in Postgres                          |
| `TEMPLATE_NOT_EMBEDDED` | `422` | `/compare`                            | Template has no vectors yet                                    |
| `NO_CLAUSES_FOUND`      | `422` | `/export/*`                           | Analysis not yet run for this contract                         |
| `THRESHOLD_NOT_MET`     | `200` | `/qa`, `/cross-query`               | No relevant clauses found (not an error — returns gracefully) |

---

## Pipeline Cheat Sheet

```
Endpoint              Triggered By          AI Models Used                    Returns
─────────────────────────────────────────────────────────────────────────────────────────
POST /analyze         BullMQ job            spaCy + BERT + embed + Claude     JSON (results to Postgres)
POST /qa              User chat             embed + Qdrant + Claude stream     JSON + streaming
POST /compare         User picks template   embed + Qdrant + Claude            JSON
GET  /clauses         Page load             ─ none (DB read only) ─            JSON
POST /export/redline  Export button         Claude (suggestions only)          DOCX binary
POST /export/summary  Export button         Claude (summary paragraph)         PDF binary
POST /cross-query     User chat multi-doc   embed + Qdrant ×N + Claude         JSON
```

### The Golden Rule

```
NestJS  →  checks WHO you are + WHETHER you're allowed
FastAPI →  does the actual AI/ML work, trusts NestJS already gated the request
```

---

*LegalLens API Contract v1.0 · FastAPI AI Service · Internal use only*
