# POST /legallens/analyze

## Endpoint Format
* **URL**: `POST /legallens/analyze`
* **Content-Type**: `application/json`

## Request Format
```json
{
  "contract_id": "string (uuid)",
  "s3_key": "string",
  "org_id": "string (uuid)",
  "file_name": "string",
  "mime_type": "string"
}
```

## Response Format
```json
{
  "status": "processing",
  "contract_id": "string (uuid)"
}
```

## Full Ingestion Workflow & Pipeline
1. **Request Reception**: The endpoint validates the incoming payload fields.
2. **State Initialization**: Upserts a record in the PostgreSQL `contracts` table with `status = 'processing'`.
3. **Task Delegation**: Adds the `run_analyze_pipeline` background task to the FastAPI event loop thread pool.
4. **Cloud Download**: Downloads the document from Cloudinary using `s3_key`.
5. **Text Extraction**: Uses `pdfplumber` for text extraction, falling back to `pytesseract` OCR if less than 100 characters are found.
6. **Sentence Segmentation**: Uses lightweight `spaCy` boundaries and merges lines into clauses (>150 characters).
7. **Risk Classification**: Classifies each clause's risk score using keyword heuristics (`low`, `medium`, `high`, `critical`).
8. **Claude Explanation**: Generates layman translations of high/critical clauses using Groq's custom Llama 3 models.
9. **Vector Generation**: Converts clauses into 384-dimension embeddings via the Hugging Face `AsyncInferenceClient`.
10. **Vector Storage**: Upserts vectors into organization-scoped Qdrant collections.
11. **PostgreSQL Save**: Commits all clauses, risk score computations, and status = `done` to the database.
