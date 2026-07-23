import asyncio
import grpc
from concurrent import futures

from lib.protos import traceum_pb2_grpc, polymind_pb2_grpc

_main_loop: asyncio.AbstractEventLoop | None = None

def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop

def get_main_loop() -> asyncio.AbstractEventLoop:
    if _main_loop is None:
        raise RuntimeError("Main event loop not set. Call set_main_loop() in lifespan.")
    return _main_loop

def serve() -> None:
    from api.grpc.traceum.servicer import TraceumUpliftServicer
    from api.grpc.polymind.servicer import PolyMindServicer
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    traceum_pb2_grpc.add_TraceumUpliftServicer_to_server(TraceumUpliftServicer(), server)

    add_polymind = getattr(polymind_pb2_grpc, "add_PolyMindServiceServicer_to_server")
    add_polymind(PolyMindServicer(), server)

    server.add_insecure_port("[::]:50051")
    server.start()
    print("gRPC server running on port 50051 (Traceum + PolyMind)")
    server.wait_for_termination()
