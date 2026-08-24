from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, status

from .commerce_login import (
    Checkout,
    CodeRequest,
    CodeVerification,
    FulfillmentStage,
    OrderLogin,
    OrderRecord,
    OrderView,
)
from .otp_login import InfraiSms, SmsApiError


def build_app(login: OrderLogin) -> FastAPI:
    app = FastAPI(title="Verified order updates")

    @app.post("/login/code", status_code=status.HTTP_202_ACCEPTED)
    def request_code(request: CodeRequest) -> dict[str, str]:
        try:
            login.request_code(request)
        except PermissionError as exc:
            raise HTTPException(status_code=404, detail="Order not found") from exc
        except SmsApiError as exc:
            raise HTTPException(status_code=502, detail="SMS request rejected") from exc
        return {"status": "code_sent", "order_id": request.order_id}

    @app.post("/login/verify", response_model=OrderView)
    def verify_code(request: CodeVerification) -> OrderView:
        try:
            return login.verify_and_release(request)
        except PermissionError as exc:
            raise HTTPException(status_code=404, detail="Order not found") from exc
        except SmsApiError as exc:
            raise HTTPException(status_code=401, detail="Code was not accepted") from exc

    return app


def create_app() -> FastAPI:
    phone = os.environ.get("DEMO_PHONE", "+14155550123")
    orders = {
        "ORDER-1042": OrderRecord(
            order_id="ORDER-1042",
            phone=phone,
            checkout=Checkout(status="paid", total="86.40", currency="USD"),
            fulfillment=FulfillmentStage.PACKING,
            receipt_id="RCPT-1042",
        )
    }
    return build_app(
        OrderLogin(InfraiSms(os.environ.get("INFRAI_API_KEY", "")), orders)
    )


app = create_app()
