# POST /legallens/cross-query

## Endpoint Format
* **URL**: `POST /legallens/cross-query`
* **Content-Type**: `application/json`

## Request Format
```json
{
  "matter_id": "string",
  "contract_ids": ["string (uuid)"],
  "question": "string",
  "top_k_per_contract": 3
}
```

## Response Format
```json
{
  "message": "Mock cross query response"
}
```

## Workflow
* Query search matches across multiple contracts simultaneously (Currently returns mock values).
