# GET /legallens/clauses

## Endpoint Format
* **URL**: `GET /legallens/clauses`
* **Query Parameters**:
  * `contract_id` (required, string uuid)
  * `risk_filter` (optional, comma-separated string e.g. `high,critical`)
  * `page` (optional, default: `1`)
  * `page_size` (optional, default: `50`)

## Request Format
* Direct GET request with query params.

## Response Format
```json
{
  "contract_id": "string (uuid)",
  "total_clauses": 111,
  "clauses": [
    {
      "id": "string (uuid)",
      "contract_id": "string (uuid)",
      "text": "string",
      "start_char": 20659,
      "end_char": 20995,
      "page_no": 7,
      "risk_label": "low",
      "risk_score": 99,
      "confidence": 0.99,
      "explanation": null,
      "created_at": "timestamp"
    }
  ],
  "page": 1,
  "page_size": 50
}
```

## Workflow
1. Looks up the total number of clauses for the target contract from the PostgreSQL `clauses` table.
2. Formulates a dynamic SQL query filtering by `risk_label` array if `risk_filter` query param is present.
3. Orders results by `risk_score` descending.
4. Applies `LIMIT` and `OFFSET` pagination math.
5. Returns the rows as JSON.
