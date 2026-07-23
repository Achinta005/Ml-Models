from typing import Any
import pandas as pd
import grpc

from lib.protos import traceum_pb2, traceum_pb2_grpc
from lib.utils.model_loader import models

UpliftResponse = traceum_pb2.UpliftResponse  # type: ignore[attr-defined]

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
