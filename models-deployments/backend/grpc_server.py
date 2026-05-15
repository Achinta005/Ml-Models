# grpc_server.py
import asyncio
import grpc
import threading
import json
from concurrent import futures
from typing import Any
import pandas as pd

import traceum_pb2
import traceum_pb2_grpc
import polymind_pb2
import polymind_pb2_grpc  # type: ignore[import]

from utils.model_loader import models
from Polymind.pipeline.pipeline import run_injest_pipeline, run_query_pipeline, get_indexer

UpliftResponse = traceum_pb2.UpliftResponse  # type: ignore[attr-defined]
UpliftRequest  = traceum_pb2.UpliftRequest   # type: ignore[attr-defined]

_main_loop: asyncio.AbstractEventLoop | None = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


def _get_main_loop() -> asyncio.AbstractEventLoop:
    if _main_loop is None:
        raise RuntimeError("Main event loop not set. Call set_main_loop() in lifespan.")
    return _main_loop


# ── Existing Servicer ─────────────────────────────────────────
class TraceumUpliftServicer(traceum_pb2_grpc.TraceumUpliftServicer):
    def PredictUplift(self, request: Any, context: Any) -> Any:
        feature_cols = [f"f{i}" for i in range(12)]
        input_df = pd.DataFrame(
            [[request.f0, request.f1, request.f2, request.f3,
              request.f4, request.f5, request.f6, request.f7,
              request.f8, request.f9, request.f10, request.f11]],
            columns=feature_cols,
        )

        if (
            models.traceum_treated_model is None
            or models.traceum_control_model is None
            or models.traceum_s_model is None
        ):
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Traceum models not loaded yet")
            return UpliftResponse()  # type: ignore[operator]

        treated_model = models.traceum_treated_model
        control_model = models.traceum_control_model
        s_model       = models.traceum_s_model

        p1_t: float = float(treated_model.predict_proba(input_df)[0, 1])
        p0_t: float = float(control_model.predict_proba(input_df)[0, 1])
        uplift_t = p1_t - p0_t

        input_t1 = input_df.copy()
        input_t1["treatment"] = 1
        input_t0 = input_df.copy()
        input_t0["treatment"] = 0

        p1_s: float = float(s_model.predict_proba(input_t1)[0, 1])
        p0_s: float = float(s_model.predict_proba(input_t0)[0, 1])
        uplift_s = p1_s - p0_s

        avg_uplift = (uplift_t + uplift_s) / 2

        return UpliftResponse(  # type: ignore[operator]
            success=True,
            uplift_t=round(uplift_t, 4),
            uplift_s=round(uplift_s, 4),
            avg_uplift=round(avg_uplift, 4),
            send_ad=avg_uplift > 0.01,
        )


# ── PolyMind Servicer ─────────────────────────────────────────
class PolyMindServicer:

    def IngestDocument(self, request: Any, context: Any) -> Any:
        loop = _get_main_loop()

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
        loop = _get_main_loop()
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


# ── Server bootstrap ──────────────────────────────────────────
def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    traceum_pb2_grpc.add_TraceumUpliftServicer_to_server(TraceumUpliftServicer(), server)

    add_polymind = getattr(polymind_pb2_grpc, "add_PolyMindServiceServicer_to_server")
    add_polymind(PolyMindServicer(), server)

    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC server running on port 50051 (Traceum + PolyMind)")
    server.wait_for_termination()


if __name__ == "__main__":
    serve()