# POST /legallens/qa

## Endpoint Format
* **URL**: `POST /legallens/qa`
* **Content-Type**: `application/json`

## Request Format
```json
{
  "contract_id": "string (uuid)",
  "question": "string",
  "conversation_history": [
    {
      "role": "user | assistant",
      "content": "string"
    }
  ],
  "top_k": 5
}
```

## Response Format
```json
{
  "answer": "string",
  "citations": [
    {
      "clause_id": "string (uuid)",
      "contract_id": "string (uuid)",
      "page_no": 2,
      "text": "string",
      "relevance_score": 0.88
    }
  ],
  "found_relevant_clauses": true
}
```

## QA RAG Workflow
1. **Fetch Org ID**: Looks up `org_id` in PostgreSQL for the matching `contract_id` to enforce data isolation boundaries.
2. **Retrieve Context (Qdrant)**: Generates query embeddings via the Hugging Face `AsyncInferenceClient` and searches the collection for `top_k` matches matching `contract_id`.
3. **Draft Answer**: Binds the query, historical conversation, and matching text snippets together, prompting the Groq `llama-3.3-70b-versatile` model to synthesize a contextual answer.
