import asyncio
import json
import grpc
from typing import Any

from lib.protos import polymind_pb2
from services.polymind.pipeline.pipeline import run_injest_pipeline, run_query_pipeline, get_indexer
from api.grpc.server import get_main_loop

class PolyMindServicer:

    def IngestDocument(self, request: Any, context: Any) -> Any:
        loop = get_main_loop()

        # Schedule coroutine on the main uvicorn loop — fire and forget
        asyncio.run_coroutine_threadsafe(
            run_injest_pipeline(
                download_url=request.download_url,
                doc_id=request.doc_id,
                filename=request.filename,
                user_id=request.user_id,
                size_bytes=request.size_bytes,
            ),
            loop,
        )

        return polymind_pb2.IngestResponse(  # type: ignore[attr-defined]
            doc_id=request.doc_id,
            status="processing",
        )

    def DeleteIndex(self, request: Any, context: Any) -> Any:
        try:
            get_indexer().delete(request.doc_id)
            return polymind_pb2.DeleteResponse(  # type: ignore[attr-defined]
                deleted=True,
                doc_id=request.doc_id,
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return polymind_pb2.DeleteResponse(  # type: ignore[attr-defined]
                deleted=False,
                doc_id=request.doc_id,
            )

    def QueryDocuments(self, request: Any, context: Any) -> Any:
        loop = get_main_loop()
        try:
            future = asyncio.run_coroutine_threadsafe(
                run_query_pipeline(
                    question=request.question,
                    document_ids=list(request.document_ids),
                    user_id=request.user_id,
                    top_k=request.top_k or 3,
                ),
                loop,
            )
            # Block gRPC thread until query completes (query is fast)
            messages, citations, _ = future.result(timeout=30)

            proto_citations = [
                polymind_pb2.Citation(  # type: ignore[attr-defined]
                    doc_name=c["docName"],
                    page=c["page"],
                    chunk=c["chunk"],
                )
                for c in citations
            ]

            return polymind_pb2.QueryResponse(  # type: ignore[attr-defined]
                success=True,
                answer="",
                citations=proto_citations,
                messages_json=json.dumps(messages),
            )

        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return polymind_pb2.QueryResponse(  # type: ignore[attr-defined]
                success=False,
                error=str(e),
            )
