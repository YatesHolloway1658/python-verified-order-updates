from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, Field

from .otp_login import SmsReply


class FulfillmentStage(StrEnum):
    PACKING = "packing"
    SHIPPED = "shipped"


class CodeRequest(BaseModel):
    order_id: str = Field(min_length=1, max_length=64)
    phone: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")


class CodeVerification(CodeRequest):
    code: str = Field(pattern=r"^[0-9]{4,8}$")


class Checkout(BaseModel):
    status: str
    total: str
    currency: str


class OrderView(BaseModel):
    order_id: str
    checkout: Checkout
    fulfillment: FulfillmentStage
    receipt_id: str
    customer_update: str


class SmsGateway(Protocol):
    def send_code(self, phone: str, idempotency_key: str) -> SmsReply:
        raise NotImplementedError

    def verify_code(
        self, phone: str, code: str, idempotency_key: str
    ) -> SmsReply:
        raise NotImplementedError


@dataclass(frozen=True)
class OrderRecord:
    order_id: str
    phone: str
    checkout: Checkout
    fulfillment: FulfillmentStage
    receipt_id: str


class OrderLogin:
    def __init__(self, sms: SmsGateway, orders: dict[str, OrderRecord]) -> None:
        self._sms = sms
        self._orders = orders

    def request_code(self, request: CodeRequest) -> None:
        order = self._owned_order(request)
        self._sms.send_code(order.phone, f"order-login:{order.order_id}:send")

    def verify_and_release(self, request: CodeVerification) -> OrderView:
        order = self._owned_order(request)
        digest = hashlib.sha256(request.code.encode("ascii")).hexdigest()[:16]
        self._sms.verify_code(
            order.phone,
            request.code,
            f"order-login:{order.order_id}:verify:{digest}",
        )
        update = (
            "Your order has shipped."
            if order.fulfillment == FulfillmentStage.SHIPPED
            else "Payment received; the warehouse is packing your order."
        )
        return OrderView(
            order_id=order.order_id,
            checkout=order.checkout,
            fulfillment=order.fulfillment,
            receipt_id=order.receipt_id,
            customer_update=update,
        )

    def _owned_order(self, request: CodeRequest) -> OrderRecord:
        order = self._orders.get(request.order_id)
        if order is None or order.phone != request.phone:
            raise PermissionError("Order and phone do not match")
        return order
