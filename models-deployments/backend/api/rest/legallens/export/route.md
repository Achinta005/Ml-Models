# POST /legallens/export/redline & POST /legallens/export/summary

## 1. POST /legallens/export/redline

### Endpoint Format
* **URL**: `POST /legallens/export/redline`
* **Content-Type**: `application/json`

### Request Format
```json
{
  "contract_id": "string (uuid)",
  "org_id": "string (uuid)",
  "include_suggestions": true,
  "include_executive_summary": true
}
```

### Response Format
* **Content-Type**: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
* **Returns**: Binary stream of a DOCX document containing the contract clauses with critical/high risk labels highlighted in red/orange respectively.

---

## 2. POST /legallens/export/summary

### Endpoint Format
* **URL**: `POST /legallens/export/summary`
* **Content-Type**: `application/json`

### Request Format
```json
{
  "contract_id": "string (uuid)",
  "org_id": "string (uuid)",
  "include_suggestions": true,
  "include_executive_summary": true
}
```

### Response Format
* **Status**: `501 Not Implemented` (Mock placeholder for PDF compilation with WeasyPrint).
