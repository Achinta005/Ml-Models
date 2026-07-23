# POST /legallens/compare

## Endpoint Format
* **URL**: `POST /legallens/compare`
* **Content-Type**: `application/json`

## Request Format
```json
{
  "contract_id": "string (uuid)",
  "template_id": "string",
  "org_id": "string (uuid)",
  "similarity_threshold": 0.78
}
```

## Response Format
```json
{
  "message": "Mock compare response",
  "match_score": 100
}
```

## Workflow
* Compare contract clauses against standard template libraries to determine variations or deviation risks (Currently returns mock values).
