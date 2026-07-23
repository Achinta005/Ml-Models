from fastapi import APIRouter
from lib.db import connection as db

router = APIRouter()

@router.get("/clauses")
async def get_clauses(
    contract_id: str, risk_filter: str = None, page: int = 1, page_size: int = 50
):
    async with db.get_pool().acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM clauses WHERE contract_id = $1", contract_id
        )

        query = "SELECT * FROM clauses WHERE contract_id = $1"
        args = [contract_id]

        if risk_filter:
            risks = [r.strip() for r in risk_filter.split(",")]
            query += f" AND risk_label = ANY(${len(args) + 1}::text[])"
            args.append(risks)

        query += (
            f" ORDER BY risk_score DESC LIMIT ${len(args) + 1} OFFSET ${len(args) + 2}"
        )
        args.extend([page_size, (page - 1) * page_size])

        rows = await conn.fetch(query, *args)

    return {
        "contract_id": contract_id,
        "total_clauses": total,
        "clauses": [dict(r) for r in rows],
        "page": page,
        "page_size": page_size,
    }
